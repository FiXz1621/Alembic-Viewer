"""Custom PyInstaller hook for babel - include only essential locales."""
from PyInstaller.utils.hooks import collect_data_files

# Solo incluir los archivos esenciales de babel, sin locale-data
datas = []

# Excluir locale-data que pesa 32MB
excludes = ['babel.locale-data']
