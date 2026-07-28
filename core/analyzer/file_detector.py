from pathlib import Path

from core.models.document_profile import DocumentProfile


class FileDetector:
    """
    Odpowiada za analizę informacji z systemu plików.
    """

    def analyze(self, profile: DocumentProfile) -> DocumentProfile:

        path = Path(profile.path)

        profile.exists = path.exists()

        profile.is_file = path.is_file()

        if profile.exists and profile.is_file:
            profile.size = path.stat().st_size

            profile.is_empty = profile.size == 0

        else:
            profile.size = 0

            profile.is_empty = True

        return profile
