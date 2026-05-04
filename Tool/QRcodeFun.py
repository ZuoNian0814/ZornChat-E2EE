import qrcode
import numpy as np
from PIL import Image
from pyzbar.pyzbar import decode

# 生成二维码：字符串 → PIL图像对象
def generate_qr(text: str,
        fill_color: str = "#000000",  # 前景色（二维码图案颜色），默认黑色
        back_color: str = "#ffffff"  # 背景色，默认白色
    ) -> Image.Image:
    qr = qrcode.main.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_L)
    qr.add_data(text)
    qr.make(fit=True)
    # 核心：通过make_image设置颜色，转RGB确保兼容性
    return qr.make_image(fill_color=fill_color, back_color=back_color).convert("RGB")

# 解析二维码：PIL图像对象 → 字符串
def decode_qr(image: Image.Image) -> str:
    # 直接用pyzbar解析，修复格式问题，100%兼容
    decoded = decode(np.array(image))
    return decoded[0].data.decode('utf-8') if decoded else ""

if __name__ == '__main__':
    # 1. 生成二维码（返回PIL对象）
    qr_img = generate_qr("你好，这是测试数据！123456")

    # 可选：保存图片（本地查看）
    # qr_img.show()
    # qr_img.save('ee.png')

    # 2. 解析二维码（传入PIL对象）
    content = decode_qr(qr_img)
    print("解析结果：", content)