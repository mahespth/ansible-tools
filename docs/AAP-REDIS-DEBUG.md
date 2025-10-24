
# AAP Redis issues and debug

status of services:
  https://access.redhat.com/solutions/7129046
  https://aap.local/api/gateway/v1/status

```json
{
  "status": "failed"
  "service_name": "redis"
  "nodes": {}
  "response": {
    "status": "failed",
    "mode": "standalone"
   }
  }
```

```bash
ansible all -b -m shell -a '
set -e
{
  cmd="redis-cli -s /run/redis/redis.sock"
  echo "=== $(hostname) ==="
  $cmd PING
  $cmd INFO all
  $cmd CONFIG GET \*
  $cmd LATENCY DOCTOR
  echo "SLOWLOG LEN:" $( $cmd SLOWLOG LEN )
  $cmd SLOWLOG GET 25
  $cmd CLIENT LIST
  $cmd MEMORY STATS
  $cmd MEMORY DOCTOR
  echo "DBSIZE:" $( $cmd DBSIZE )
} 2>&1
'
```

    
