FROM python:3.12

WORKDIR /app

COPY . /app/

RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    curl \
    vim \
    wget \
    net-tools


RUN pip install --upgrade pip

RUN pip install -r requirements.txt

EXPOSE 8501

CMD ["streamlit","run","app.py","--server.port=8501", "--server.address=0.0.0.0"]


