@echo off
call "%USERPROFILE%\miniconda3\Scripts\activate.bat" sso
cd /d C:\painel_sso
streamlit run app.py
pause