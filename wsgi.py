import sys
import os

# PythonAnywhere 会在 /home/<username>/<project> 下运行
# 把项目目录加到 Python 路径
project_dir = os.path.dirname(os.path.abspath(__file__))
if project_dir not in sys.path:
    sys.path.insert(0, project_dir)

from app import app as application
