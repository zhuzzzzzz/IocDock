cd prometheus/
rm im-prometheus.yml
cp prometheus.yml ./im-prometheus.yml
cat ../scrape-config.yaml >> im-prometheus.yml
./prometheus --config.file=im-prometheus.yml
