"""Dialogues réutilisables (import SRT masse, profils, OpenSubtitles, etc.)."""

from howimetyourcorpus.app.dialogs.opensubtitles_download import OpenSubtitlesDownloadDialog
from howimetyourcorpus.app.dialogs.profiles import ProfilesDialog
from howimetyourcorpus.app.dialogs.subtitle_batch_import import SubtitleBatchImportDialog

__all__ = ["OpenSubtitlesDownloadDialog", "ProfilesDialog", "SubtitleBatchImportDialog"]
