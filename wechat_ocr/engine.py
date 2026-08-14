"""面向调用方（尤其是 AI）的高层同步 OCR 接口。

在底层 :class:`OcrManager` 之上封装一层，把「设路径 / 设回调 / 启动 / 逐个
DoOCRTask / 忙等 / 关闭」这一整套繁琐流程收敛成一次同步调用，直接返回
结构化结果。

典型用法::

    from wechat_ocr import ocr

    result = ocr("path/to/image.png")
    print(result.text)                 # 完整识别文本（按行拼接）
    for item in result.items:          # 逐行：文本 + 坐标 + 置信度
        print(item.text, item.left, item.top, item.confidence)

批量 / 复用同一服务::

    from wechat_ocr import WeChatOcr

    with WeChatOcr() as client:
        r1 = client.recognize("a.png")
        r2 = client.recognize("b.png")
"""
import os
import time
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .ocr_manager import OcrManager

# 包所在目录（wechat_ocr/），仓库根目录在其上一级，bin/ 位于仓库根
_PKG_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _PKG_DIR.parent

DEFAULT_EXE_PATH = str(_REPO_ROOT / "bin" / "WeChatOCR" / "WeChatOCR.exe")
DEFAULT_USER_LIB_DIR = str(_REPO_ROOT / "bin")


@dataclass
class OcrItem:
    """单行识别结果。"""
    text: str
    left: Optional[float] = None
    top: Optional[float] = None
    right: Optional[float] = None
    bottom: Optional[float] = None
    confidence: Optional[float] = None
    pos: Any = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "left": self.left,
            "top": self.top,
            "right": self.right,
            "bottom": self.bottom,
            "confidence": self.confidence,
            "pos": self.pos,
        }


@dataclass
class OcrResult:
    """一次识别的整体结果。"""
    task_id: Optional[int] = None
    items: List[OcrItem] = field(default_factory=list)

    @property
    def text(self) -> str:
        """完整识别文本，按行用换行符拼接。"""
        return "\n".join(item.text for item in self.items)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "taskId": self.task_id,
            "text": self.text,
            "items": [item.to_dict() for item in self.items],
        }


class WeChatOcr:
    """高层同步 OCR 客户端。

    内部复用 :class:`OcrManager`，把异步回调结果映射成阻塞等待，调用方无需
    关心 task_id、回调、忙等与关闭。支持上下文管理器，便于一次启动、多次识别。
    """

    def __init__(
        self,
        wechat_dir: Optional[str] = None,
        exe_path: Optional[str] = None,
        timeout: float = 30.0,
    ) -> None:
        """
        :param wechat_dir: mmmojo.dll 所在目录（默认仓库根 bin/）
        :param exe_path: WeChatOCR.exe 路径（默认仓库根 bin/WeChatOCR/WeChatOCR.exe）
        :param timeout: 单次识别 / 连接超时秒数
        """
        wechat_dir = wechat_dir or DEFAULT_USER_LIB_DIR
        exe_path = exe_path or DEFAULT_EXE_PATH
        if not os.path.exists(exe_path):
            raise FileNotFoundError(f"WeChatOCR.exe 不存在: {exe_path}")
        if not os.path.isdir(wechat_dir):
            raise FileNotFoundError(f"mmmojo.dll 所在目录不存在: {wechat_dir}")

        self._timeout = timeout
        self._started = False
        self._results: Dict[str, dict] = {}
        self._events: Dict[str, threading.Event] = {}
        self._lock = threading.Lock()

        self._manager = OcrManager(wechat_dir)
        self._manager.SetExePath(exe_path)
        self._manager.SetUsrLibDir(wechat_dir)
        self._manager.SetOcrResultCallback(self._on_result)

    # ------------------------------------------------------------------ 生命周期
    def start(self) -> None:
        """启动 WeChatOCR 服务（幂等）。"""
        if self._started:
            return
        self._manager.StartWeChatOCR()
        self._started = True
        self.wait_ready(self._timeout)

    def wait_ready(self, timeout: Optional[float] = None) -> None:
        """阻塞等待 OCR 服务连接成功，超时抛 TimeoutError。"""
        timeout = self._timeout if timeout is None else timeout
        deadline = time.time() + timeout
        while not self._manager.m_connect_state.value:
            if time.time() > deadline:
                raise TimeoutError("WeChatOCR 服务连接超时")
            time.sleep(0.05)

    def close(self) -> None:
        """停止并释放 WeChatOCR 服务（幂等）。"""
        if not self._started:
            return
        try:
            self._manager.KillWeChatOCR()
        finally:
            self._started = False

    def __enter__(self) -> "WeChatOcr":
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    # ------------------------------------------------------------------ 识别接口
    def recognize(self, image_path: str, timeout: Optional[float] = None) -> OcrResult:
        """同步识别单张图片，阻塞直到结果返回。"""
        self.start()
        timeout = self._timeout if timeout is None else timeout

        key = os.path.abspath(image_path)
        event = threading.Event()
        with self._lock:
            self._events[key] = event
            self._results.pop(key, None)

        try:
            self._manager.DoOCRTask(image_path)
        except Exception:
            with self._lock:
                self._events.pop(key, None)
            raise

        if not event.wait(timeout):
            with self._lock:
                self._events.pop(key, None)
            raise TimeoutError(f"识别超时: {image_path}")

        with self._lock:
            self._events.pop(key, None)
            raw = self._results.pop(key, None)
        if raw is None:
            raise RuntimeError(f"未获取到识别结果: {image_path}")
        return self._parse_result(raw)

    def recognize_many(self, image_paths: List[str], timeout: Optional[float] = None) -> List[OcrResult]:
        """顺序识别多张图片，复用同一服务。"""
        return [self.recognize(p, timeout=timeout) for p in image_paths]

    # ------------------------------------------------------------------ 内部
    def _on_result(self, img_path: str, results: dict) -> None:
        """底层回调（运行于 mojo 线程），把结果写入并按路径唤醒等待者。"""
        key = os.path.abspath(img_path)
        with self._lock:
            self._results[key] = results
            event = self._events.get(key)
        if event:
            event.set()

    @staticmethod
    def _parse_result(results: dict) -> OcrResult:
        items = []
        for r in results.get("ocrResult", []):
            loc = r.get("location", {}) or {}
            items.append(OcrItem(
                text=r.get("text", ""),
                left=loc.get("left"),
                top=loc.get("top"),
                right=loc.get("right"),
                bottom=loc.get("bottom"),
                confidence=r.get("rate"),
                pos=r.get("pos"),
            ))
        return OcrResult(task_id=results.get("taskId"), items=items)


def ocr(image_path: str, **kwargs) -> OcrResult:
    """一次性识别：自动启动服务、识别并关闭。适合单张 / 低频调用。"""
    with WeChatOcr(**kwargs) as client:
        return client.recognize(image_path)
