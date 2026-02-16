




# Podman

podman volume create grafana-data


## Podman systemd service
podman generate systemd --name grafana --files --new
mkdir -p ~/.config/systemd/user
mv container-grafana.service ~/.config/systemd/user/

systemctl --user daemon-reload
systemctl --user enable --now container-grafana.service



# Prometheus
podman volume create prom-data

podman run -d --name prometheus \
  -p 9090:9090 \
  -v "$(pwd)/prometheus.yml:/etc/prometheus/prometheus.yml:Z,ro" \
  -v prom-data:/prometheus:Z \
  docker.io/prom/prometheus:latest
