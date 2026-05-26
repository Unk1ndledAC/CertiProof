import fitz  # PyMuPDF

def crop_by_margins(input_path, output_path, margins, page_num=0):
    """
    根据四周的边距裁剪PDF。

    参数:
    input_path (str): 输入PDF路径
    output_path (str): 输出PDF路径
    margins (tuple): 裁剪边距 (left, right, top, bottom)
                     对应你描述的 (x1, x2, y1, y2)
    page_num (int): 页面索引，默认为0（第一页）
    """
    # 1. 打开文档
    doc = fitz.open(input_path)
    page = doc[page_num]
    
    # 2. 获取原始页面尺寸
    # rect 包含: x0(左上x), y0(左上y), x1(右下x), y1(右下y)
    # 对于标准页面，x0=0, y0=0
    original_rect = page.rect
    width = original_rect.width
    height = original_rect.height
    
    # 3. 解析边距
    left_margin   = margins[0] # x1
    right_margin  = margins[1] # x2
    top_margin    = margins[2] # y1
    bottom_margin = margins[3] # y2
    
    # 4. 计算新的裁剪坐标 (x0, y0, x1, y1)
    # 新左上角 = 原左上角 + 左边距/上边距
    new_x0 = original_rect.x0 + left_margin
    new_y0 = original_rect.y0 + top_margin
    
    # 新右下角 = 原右下角 - 右边距/下边距
    new_x1 = original_rect.x1 - right_margin
    new_y1 = original_rect.y1 - bottom_margin
    
    # 5. 简单的错误检查（防止裁剪区域无效）
    if new_x0 >= new_x1 or new_y0 >= new_y1:
        print("错误：裁剪边距过大，导致裁剪区域无效！")
        doc.close()
        return

    # 6. 应用裁剪
    crop_rect = (new_x0, new_y0, new_x1, new_y1)
    page.set_cropbox(crop_rect)
    
    # 7. 保存
    doc.save(output_path)
    doc.close()
    print(f"✅ 裁剪完成！已保存至: {output_path}")
    print(f"   裁剪区域坐标: {crop_rect}")

# --- 使用示例 ---
if __name__ == "__main__":
    input_pdf = "SOTA-Table.pdf"
    output_pdf = "SOTA-Table crop.pdf"
    
    # 定义边距: (左边x1, 右边x2, 上边y1, 下边y2)
    # 例如：左边裁50，右边裁50，上边裁30，下边裁30
    my_margins = (41, 41, 195, 187)
    
    crop_by_margins(input_pdf, output_pdf, my_margins)