"""
atss_gnn.py
============
GNN-based formula embedding for the Adaptive Tactic Synthesis System (ATSS).

Instead of using simple cosine-similarity over formula hashes, this module
uses a Graph Neural Network (GNN) to learn formula representations from
the clause-variable bipartite graph structure.

Architecture:
  - Variables → nodes with learnable initial embeddings
  - Clauses → hyperedges connecting their variable nodes
  - 3-layer GIN (Graph Isomorphism Network) message passing
  - Global pooling → tactic suitability score (1 scalar per tactic)

Training:
  - Online learning: each proof attempt generates a (formula_graph, tactic_used, success) triplet
  - Binary cross-entropy loss on tactic suitability
  - Trained on GPU (RTX 4070 Ti SUPER) with Adam optimizer

Usage:
  from src.atss_gnn import GNNATSS, FormulaGraph
  gnn_atss = GNNATSS(device='cuda')
  gnn_atss.update(formula, tactic_name, success=True)
  scores = gnn_atss.rank_tactics(formula, tactic_names)
"""

from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, List, Optional, Tuple, Set
from collections import defaultdict

# Lazy import of torch_geometric (may not be available)
try:
    from torch_geometric.nn import GINConv, global_mean_pool
    from torch_geometric.data import Data
    HAS_TG = True
except ImportError:
    HAS_TG = False


# ──────────────────────────────────────────────────────────────────────────────
# Formula → Graph conversion
# ──────────────────────────────────────────────────────────────────────────────

class FormulaGraph:
    """
    Convert a propositional clause set into a bipartite graph suitable
    for GNN processing.

    Graph structure:
      - Node 0 .. n_vars-1: variable nodes
      - Edge i → j: variable i appears in clause j
      - Edge is labeled +1 (positive) or -1 (negative polarity)
    """

    def __init__(self, var_names: List[str],
                 clauses: List[Set[Tuple[str, bool]]]) -> None:
        """
        Parameters
        ----------
        var_names : list of str
            Ordered variable names.
        clauses : list of sets of (var_name, is_positive) tuples
            Clause set in the internal representation.
        """
        self.var_names = var_names
        self.var_index = {v: i for i, v in enumerate(var_names)}
        self.n_vars = len(var_names)
        self.n_clauses = len(clauses)

        # Build edge list (variable → clause bipartite edges)
        edge_index = []   # [2, E]
        edge_attr = []    # [E] polarity (+1 / -1)

        for c_idx, clause in enumerate(clauses):
            for var, is_pos in clause:
                v_idx = self.var_index.get(var)
                if v_idx is not None:
                    # Variable node → clause node (offset by n_vars)
                    edge_index.append([v_idx, self.n_vars + c_idx])
                    edge_attr.append(1.0 if is_pos else -1.0)

        self.edge_index = edge_index
        self.edge_attr = edge_attr

    def to_pyg_data(self) -> 'Data':
        """Convert to PyTorch Geometric Data object."""
        if not HAS_TG:
            raise RuntimeError(
                "torch_geometric is required. "
                "Install with: pip install torch_geometric")

        if not self.edge_index:
            # Empty graph (no edges)
            x = torch.zeros(self.n_vars + self.n_clauses, 1)
            edge_index = torch.zeros((2, 0), dtype=torch.long)
            edge_attr = torch.zeros(0, 1)
            return Data(x=x, edge_index=edge_index, edge_attr=edge_attr,
                        num_nodes=self.n_vars + self.n_clauses)

        import torch
        x = torch.zeros(self.n_vars + self.n_clauses, 16)  # 16-dim features
        # Variable nodes get a small initial feature
        x[:self.n_vars, 0] = 1.0
        # Clause nodes get a different initial feature
        x[self.n_vars:, 1] = 1.0

        edge_index = torch.tensor(self.edge_index, dtype=torch.long).t().contiguous()
        edge_attr = torch.tensor(self.edge_attr, dtype=torch.float).unsqueeze(1)

        return Data(x=x, edge_index=edge_index, edge_attr=edge_attr,
                    num_nodes=self.n_vars + self.n_clauses)


# ──────────────────────────────────────────────────────────────────────────────
# GNN Model
# ──────────────────────────────────────────────────────────────────────────────

class FormulaEncoder(nn.Module):
    """
    GIN-based encoder for clause-variable graphs.

    Produces a fixed-size embedding for an input formula graph.
    """

    def __init__(self, in_dim: int = 16, hidden_dim: int = 64,
                 out_dim: int = 32, n_layers: int = 3) -> None:
        super().__init__()
        self.n_layers = n_layers
        self.convs = nn.ModuleList()
        self.norms = nn.ModuleList()

        for i in range(n_layers):
            in_d = in_dim if i == 0 else hidden_dim
            nn_inp = nn.Sequential(
                nn.Linear(in_d, hidden_dim),
                nn.ReLU(),
                nn.Linear(hidden_dim, hidden_dim))
            conv = GINConv(nn_inp)
            self.convs.append(conv)
            self.norms.append(nn.LayerNorm(hidden_dim))

        self.pool = global_mean_pool
        self.fc = nn.Linear(hidden_dim, out_dim)

    def forward(self, data: 'Data') -> torch.Tensor:
        """
        Parameters
        ----------
        data : torch_geometric.data.Data
            Graph data with x, edge_index, edge_attr.

        Returns
        -------
        torch.Tensor of shape [out_dim]
        """
        x, edge_index, batch = data.x, data.edge_index, data.batch

        for i in range(self.n_layers):
            x = self.convs[i](x, edge_index)
            x = self.norms[i](x)
            x = F.relu(x)

        # Global pooling: graph-level embedding
        graph_emb = self.pool(x, batch)  # [batch_size, hidden_dim]
        return self.fc(graph_emb)  # [batch_size, out_dim]


# ──────────────────────────────────────────────────────────────────────────────
# GNN ATSS
# ──────────────────────────────────────────────────────────────────────────────

class GNNATSS:
    """
    GNN-based Adaptive Tactic Synthesis System.

    Replaces the simple cosine-similarity ATSS with a GNN-based
    formula embedding that learns which tactics are suitable for
    which formula structures.

    The GNN is trained online during proof search: each proof attempt
    generates a training signal (success/failure) that updates the
    GNN weights.
    """

    # Default tactic names
    DEFAULT_TACTICS = [
        'assumption', 'contradiction', 'modus_ponens',
        'and_i', 'imp_i', 'not_i', 'or_i', 'iff_i',
        'solver_fallback',
    ]

    def __init__(self, device: str = 'auto',
                 hidden_dim: int = 64, embed_dim: int = 32,
                 lr: float = 1e-3) -> None:
        """
        Parameters
        ----------
        device : str
            'cuda', 'cpu', or 'auto' (use GPU if available).
        hidden_dim : int
            Hidden dimension of the GNN.
        embed_dim : int
            Output embedding dimension.
        lr : float
            Learning rate for online training.
        """
        if not HAS_TG:
            raise RuntimeError(
                "torch_geometric is required. "
                "Install with: pip install torch_geometric")

        if device == 'auto':
            device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.device = torch.device(device)

        self.tactic_names = list(self.DEFAULT_TACTICS)
        self.tactic_to_idx = {t: i for i, t in enumerate(self.tactic_names)}
        self.n_tactics = len(self.tactic_names)

        # GNN encoder
        self.encoder = FormulaEncoder(
            in_dim=16, hidden_dim=hidden_dim, out_dim=embed_dim
        ).to(self.device)

        # Tactic score head: embedding → per-tactic score
        self.score_head = nn.Linear(embed_dim, self.n_tactics).to(self.device)

        # Optimizer for online learning
        self.optimizer = torch.optim.Adam(
            list(self.encoder.parameters()) + list(self.score_head.parameters()),
            lr=lr)

        # Training buffer
        self._buffer_x: List[torch.Tensor] = []
        self._buffer_edge_index: List[torch.Tensor] = []
        self._buffer_edge_attr: List[torch.Tensor] = []
        self._buffer_target: List[int] = []  # tactic index
        self._buffer_label: List[float] = []  # 1.0 success, 0.0 failure
        self._buffer_size = 64  # train every N samples

        self._update_count = 0

    def score(self, formula_graph: FormulaGraph) -> Dict[str, float]:
        """
        Score all tactics for the given formula graph.

        Returns a dict mapping tactic name → score (higher = more suitable).
        """
        self.encoder.eval()
        with torch.no_grad():
            data = formula_graph.to_pyg_data().to(self.device)
            emb = self.encoder(data)  # [1, embed_dim]
            logits = self.score_head(emb)  # [1, n_tactics]
            probs = torch.sigmoid(logits).squeeze(0).cpu().numpy()

        return {name: float(probs[i])
                for i, name in enumerate(self.tactic_names)}

    def rank_tactics(self, formula_graph: FormulaGraph,
                     tactic_names: Optional[List[str]] = None
                     ) -> List[str]:
        """
        Return tactic names sorted by predicted suitability (best first).
        """
        scores = self.score(formula_graph)
        names = tactic_names or self.tactic_names
        return sorted(names, key=lambda t: scores.get(t, 0.5), reverse=True)

    def update(self, formula_graph: FormulaGraph,
               tactic_name: str, success: bool) -> None:
        """
        Record a (formula, tactic, outcome) triplet for online learning.

        The GNN is updated periodically (every _buffer_size samples).
        """
        data = formula_graph.to_pyg_data()
        self._buffer_x.append(data.x)
        self._buffer_edge_index.append(data.edge_index)
        self._buffer_edge_attr.append(data.edge_attr)

        tidx = self.tactic_to_idx.get(tactic_name, 0)
        self._buffer_target.append(tidx)
        self._buffer_label.append(1.0 if success else 0.0)

        if len(self._buffer_label) >= self._buffer_size:
            self._train_step()
            self._buffer_x.clear()
            self._buffer_edge_index.clear()
            self._buffer_edge_attr.clear()
            self._buffer_target.clear()
            self._buffer_label.clear()

    def _train_step(self) -> None:
        """Perform one gradient update on the accumulated buffer."""
        if not self._buffer_x:
            return

        self.encoder.train()
        self.optimizer.zero_grad()

        total_loss = 0.0
        n = len(self._buffer_label)

        for i in range(n):
            x = self._buffer_x[i].to(self.device)
            edge_index = self._buffer_edge_index[i].to(self.device)
            edge_attr = self._buffer_edge_attr[i].to(self.device)

            # Create Data object for single graph
            batch = torch.zeros(x.size(0), dtype=torch.long, device=self.device)
            from torch_geometric.data import Data
            data = Data(x=x, edge_index=edge_index,
                       edge_attr=edge_attr, batch=batch)

            emb = self.encoder(data)
            logits = self.score_head(emb)

            # Binary cross-entropy on the tactic that was tried
            target_idx = self._buffer_target[i]
            label = self._buffer_label[i]

            # Loss: BCE on the specific tactic, regularization on others
            loss = F.binary_cross_entropy_with_logits(
                logits.squeeze(0)[target_idx],
                torch.tensor(label, device=self.device))

            total_loss += loss

        total_loss = total_loss / n
        total_loss.backward()
        torch.nn.utils.clip_grad_norm_(
            list(self.encoder.parameters()) + list(self.score_head.parameters()),
            1.0)
        self.optimizer.step()
        self._update_count += 1

    def save(self, path: str) -> None:
        """Save model weights to disk."""
        torch.save({
            'encoder': self.encoder.state_dict(),
            'score_head': self.score_head.state_dict(),
            'tactic_names': self.tactic_names,
            'update_count': self._update_count,
        }, path)

    def load(self, path: str) -> None:
        """Load model weights from disk."""
        checkpoint = torch.load(path, map_location=self.device,
                                weights_only=True)
        self.encoder.load_state_dict(checkpoint['encoder'])
        self.score_head.load_state_dict(checkpoint['score_head'])
        self.tactic_names = checkpoint['tactic_names']
        self.tactic_to_idx = {t: i for i, t in enumerate(self.tactic_names)}
        self.n_tactics = len(self.tactic_names)
        self._update_count = checkpoint.get('update_count', 0)
