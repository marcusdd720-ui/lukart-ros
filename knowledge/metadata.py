"""
Knowledge Operating System (KOS)

File: knowledge/metadata.py
Sprint: F-009

Parses YAML Front Matter from Markdown documents.
"""

from dataclasses import dataclass


@dataclass
class Metadata:
    document_id: str = ""
    title: str = ""
    doc_type: str = ""
    version: str = ""
    status: str = ""


class MetadataParser:
    """Simple YAML Front Matter parser."""

    def parse(self, text: str) -> Metadata:

        metadata = Metadata()

        lines = text.splitlines()

        if not lines or lines[0].strip() != "---":
            return metadata

        for line in lines[1:]:
            line = line.strip()

            if line == "---":
                break

            if ":" not in line:
                continue

            key, value = line.split(":", 1)

            key = key.strip()
            value = value.strip()

            if key == "id":
                metadata.document_id = value

            elif key == "title":
                metadata.title = value

            elif key == "type":
                metadata.doc_type = value

            elif key == "version":
                metadata.version = value

            elif key == "status":
                metadata.status = value

        return metadata
