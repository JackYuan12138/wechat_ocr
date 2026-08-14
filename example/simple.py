"""高层接口示例：一行调用即可完成识别，无需手动管理回调/启动/关闭。"""
from wechat_ocr import WeChatOcr, ocr


def one_shot():
    # 一次性调用：自动启动服务、识别、关闭
    result = ocr(r"..\test_img\1.png")
    print("=== 一次性调用 ===")
    print(result.text)


def batch():
    # 批量：复用同一服务，逐个识别
    with WeChatOcr() as client:
        for r in client.recognize_many([r"..\test_img\1.png", r"..\test_img\2.png", r"..\test_img\3.png"]):
            print("=== 批量识别 ===")
            print(r.text)


if __name__ == "__main__":
    one_shot()
    batch()
