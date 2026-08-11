## 项目说明
本项目是使用Python来调用微信本地ocr模型，调用方法完全由[QQImpl](https://github.com/EEEEhex/QQImpl)翻译过来。也就是说该项目只是将原C++代码翻译成了纯Python实现。

#### 温馨提示

该项目自己玩玩就行，不要用于商业用途

## 使用说明

#### 安装

```bash
git clone https://github.com/JackYuan12138/wechat_ocr.git
cd wechat_ocr
pip install -e .
```

或使用 uv：

```bash
git clone https://github.com/JackYuan12138/wechat_ocr.git
cd wechat_ocr
uv sync
```

#### 依赖(必要条件)

1. Windows 系统
2. Python >= 3.12

> 项目 `bin/` 目录已自带所需的 `WeChatOCR.exe`、`mmmojo.dll` 及模型文件，无需额外安装微信。

#### 示例

> **注意**：以下示例代码需在 `example/` 目录下运行（或从项目根目录执行 `python example/ocr.py`），因为代码中的相对路径 `..\test_img\` 和 `..\bin` 是相对于 `example/` 目录的。

```python
import os
import json
import time
from wechat_ocr.ocr_manager import OcrManager, OCR_MAX_TASK_ID, OCR_DEFAULT_EXE_PATH, OCR_DEFAULT_USER_LIB_DIR


wechat_ocr_dir = OCR_DEFAULT_EXE_PATH
wechat_dir = OCR_DEFAULT_USER_LIB_DIR

def ocr_result_callback(img_path:str, results:dict):
    result_file = os.path.basename(img_path) + ".json"
    print(f"识别成功，img_path: {img_path}, result_file: {result_file}")
    with open(result_file, 'w', encoding='utf-8') as f:
       f.write(json.dumps(results, ensure_ascii=False, indent=2))

def main():
    ocr_manager = OcrManager(wechat_dir)
    # 设置 WeChatOCR.exe 路径
    ocr_manager.SetExePath(wechat_ocr_dir)
    # 设置 WeChatOCR 的 user-lib-dir（mmmojo.dll 所在目录）
    ocr_manager.SetUsrLibDir(wechat_dir)
    # 设置ocr识别结果的回调函数
    ocr_manager.SetOcrResultCallback(ocr_result_callback)
    # 启动ocr服务
    ocr_manager.StartWeChatOCR()
    # 开始识别图片
    ocr_manager.DoOCRTask(r"..\test_img\1.png")
    ocr_manager.DoOCRTask(r"..\test_img\2.png")
    ocr_manager.DoOCRTask(r"..\test_img\3.png")
    time.sleep(1)
    while ocr_manager.m_task_id.qsize() != OCR_MAX_TASK_ID:
        pass
    # 识别输出结果
    ocr_manager.KillWeChatOCR()
    

if __name__ == "__main__":
    main()
```

#### 运行结果

![result](./result.png)

## 感谢
https://github.com/kanadeblisst00/wechat_ocr
https://github.com/EEEEhex/QQImpl
