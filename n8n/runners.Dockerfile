FROM n8nio/runners:2.48.5
USER root
COPY requirements-python.txt /tmp/requirements-python.txt
RUN cd /opt/runners/task-runner-python && uv pip install --no-cache -r /tmp/requirements-python.txt
COPY python /tmp/tacctico-etl
RUN cd /opt/runners/task-runner-python && uv pip install --no-cache /tmp/tacctico-etl
COPY n8n-task-runners.json /etc/n8n-task-runners.json
USER runner
