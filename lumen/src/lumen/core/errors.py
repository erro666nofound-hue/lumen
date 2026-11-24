from __future__ import annotations


class LumenError(Exception):
    """Base exception for Lumen application with user-facing message."""

    def __init__(self, message: str, *, user_message: str | None = None) -> None:
        super().__init__(message)
        self.user_message = user_message if user_message is not None else message


class ConfigError(LumenError):
    """Configuration loading or validation error."""

    pass


class DatabaseError(LumenError):
    """Database operation error."""

    pass


class DuplicatePlaylistNameError(LumenError):
    """Một track khác đã mang đúng cái tên này (khớp từng ký tự).

    Riêng khỏi DatabaseError: không có gì hỏng cả, đây là một LUẬT. Hai track
    trùng tên là ca mà luật hoà theo tên CỐ Ý không nổ (QĐ-017: không biết cái
    nào ghép cái nào), nên F-5 §1 chặn không cho ca đó sinh ra.
    """

    pass


class PlayerError(LumenError):
    """Audio player error."""

    pass


class AuthError(LumenError):
    """Sign-in error.

    Riêng khỏi DownloadError: đăng nhập hỏng và tải nhạc hỏng là hai chuyện khác
    nhau, người dùng cần thấy hai câu thông báo khác nhau.
    """

    pass


class DownloadError(LumenError):
    """Base error for download operations."""

    pass


class InvalidUrlError(DownloadError):
    """URL is invalid or cannot be parsed."""

    pass


class UnsupportedSourceError(DownloadError):
    """URL source is not supported."""

    pass


class DuplicateTrackError(DownloadError):
    """Track already exists in library."""

    pass


class NetworkError(DownloadError):
    """Network connection or download error."""

    pass


class ExtractionError(DownloadError):
    """Audio extraction or format conversion error."""

    pass


class ImportFileError(LumenError):
    """A file the owner picked cannot become a track (missing, wrong kind, unreadable)."""

    pass


class SyncError(LumenError):
    """Sync snapshot is unusable: wrong version, or shaped in a way we cannot read."""

    pass


class PlanTooLow(LumenError):
    """Máy chủ đã nhận ra người dùng, nhưng gói của họ không mở tính năng này.

    Riêng khỏi `AuthError`: giấy tờ hoàn toàn hợp lệ. Trộn hai thứ này là app
    đá người đang trả tiền gói Free ra màn hình đăng nhập lại, trong khi thứ họ
    cần thấy là lời mời nâng cấp.
    """

    def __init__(
        self, message: str, *, plan: str = "", user_message: str | None = None
    ) -> None:
        """Ghi kèm gói hiện tại để giao diện mời nâng cấp đúng chỗ."""
        super().__init__(message, user_message=user_message)
        self.plan = plan


class StoreFull(LumenError):
    """Kho file của tài khoản đã chạm trần — DỪNG cả đợt, đừng thử bài tiếp theo.

    Tách khỏi `FileRejected` vì hai cái dẫn tới hai hành vi ngược nhau: bài này
    hỏng thì bỏ qua bài này, còn kho đầy thì mọi bài sau đều hỏng y hệt, và cứ
    thử tiếp là hàng trăm cú gọi mạng chỉ để nghe cùng một câu từ chối.

    Trần là hằng số của MÁY CHỦ (QĐ-027), nên `bytes`/`quota` đi kèm ở đây chứ
    không nướng vào app: đổi chính sách thì app cũ vẫn nói đúng số.
    """

    def __init__(
        self,
        message: str,
        *,
        bytes_used: int = 0,
        quota: int = 0,
        user_message: str | None = None,
    ) -> None:
        """Mang theo số máy chủ vừa nói, để Cài đặt hiện đúng chỗ đang đầy."""
        super().__init__(message, user_message=user_message)
        self.bytes_used = bytes_used
        self.quota = quota


class FileRejected(LumenError):
    """Kho từ chối ĐÚNG file này — bỏ qua nó, đợt vẫn đi tiếp.

    Ba cớ: file quá trần một bài, bytes không khớp địa chỉ (cột `content_hash`
    đã cũ hơn file trên đĩa), hoặc thứ tải về không băm ra đúng địa chỉ đã hỏi.
    Cả ba đều là chuyện của một dòng, không phải của tài khoản.
    """

    pass
