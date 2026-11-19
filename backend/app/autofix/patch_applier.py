import os
from typing import Dict, Any, List


class PatchApplier:
    """
    Applies a validated patch strictly to an isolated in-memory working copy of the
    uploaded source snapshot, leaving the original analysis and files completely untouched.
    """

    @staticmethod
    def build_working_copy(
        source_snapshot: Dict[str, Dict[str, Any]],
        target_file: str,
        patched_code: str,
    ) -> List[Dict[str, Any]]:
        if target_file not in source_snapshot:
            raise ValueError(f"Target file '{target_file}' not found in analysis source snapshot.")

        working_files: List[Dict[str, Any]] = []
        for fpath, finfo in source_snapshot.items():
            content = patched_code if fpath == target_file else finfo["content"]
            working_files.append({
                "file_path": fpath,
                "filename": os.path.basename(fpath),
                "content": content,
                "language": finfo.get("language", "python"),
                "lines_count": len(content.splitlines()),
                "size_bytes": len(content.encode("utf-8")),
            })
        return working_files
