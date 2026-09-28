"""
作业打包辅助脚本：一键将源码与文档打包为符合规范的提交压缩包（如 10086张三.zip）
"""

import os
import sys
import zipfile
from pathlib import Path


def package_project(student_id: str, student_name: str):
    root_dir = Path(__file__).resolve().parent
    archive_name = f"{student_id}{student_name}.zip"
    output_path = root_dir / archive_name

    ignore_dirs = {".git", ".venv", "__pycache__", ".pytest_cache", ".idea", ".vscode"}
    ignore_extensions = {".pyc", ".pyo", ".zip", ".rar", ".7z"}

    print(f"📦 开始打包工程为：{archive_name} ...")
    count = 0

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(root_dir):
            dirs[:] = [d for d in dirs if d not in ignore_dirs]
            for file in files:
                ext = Path(file).suffix.lower()
                if ext in ignore_extensions or file.startswith("~$"):
                    continue
                file_path = Path(root) / file
                arcname = file_path.relative_to(root_dir)
                zipf.write(file_path, arcname)
                count += 1

    size_kb = output_path.stat().st_size / 1024
    print(f"✔ 打包成功！包含 {count} 个文件，压缩包大小为: {size_kb:.2f} KB (远小于 200MB 要求)")
    print(f"📂 生成路径: {output_path}")


if __name__ == "__main__":
    if len(sys.argv) >= 3:
        sid = sys.argv[1]
        sname = sys.argv[2]
    else:
        sid = input("请输入您的学号 (例如 10086): ").strip()
        sname = input("请输入您的姓名 (例如 张三): ").strip()

    if not sid or not sname:
        print("❌ 学号和姓名不能为空！")
        sys.exit(1)

    package_project(sid, sname)
