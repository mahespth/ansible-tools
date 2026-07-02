# Compressing AWX / AAP PostgreSQL Backups, Steve Maher.

This document gives practical guidance for compressing AWX / Ansible Automation Platform PostgreSQL backups with a good balance between compression ratio, CPU impact, and restore speed.

## Recommended Default

For most production AAP or AWX PostgreSQL backups, use:

```bash
zstd -3 -T2
```

This gives a strong balance of:

* Good compression ratio
* Low to moderate CPU impact
* Very fast decompression during restore
* Better efficiency than traditional `gzip`
* Much lower CPU cost than `xz`

Example:

```bash
zstd -3 -T2 backup.sql -o backup.sql.zst
```

## Recommended Streaming Backup Command

If streaming directly from `pg_dump`, avoid PostgreSQL internal compression and let `zstd` handle it externally:

```bash
pg_dump -Fc -Z0 awx \
  | nice -n 10 ionice -c2 -n7 zstd -3 -T2 \
  > awx_$(date +%F).dump.zst
```

### What the options mean

| Option           | Meaning                                     |
| ---------------- | ------------------------------------------- |
| `pg_dump -Fc`    | Use PostgreSQL custom dump format           |
| `-Z0`            | Disable internal `pg_dump` compression      |
| `zstd -3`        | Use zstd compression level 3                |
| `-T2`            | Use 2 compression threads                   |
| `nice -n 10`     | Lower CPU scheduling priority               |
| `ionice -c2 -n7` | Lower disk I/O priority                     |
| `$(date +%F)`    | Add the current date to the backup filename |

This approach separates the database dump workload from the compression workload and gives better control over CPU and I/O impact.

## Restore Example

To restore a zstd-compressed custom-format dump:

```bash
zstd -dc awx.dump.zst | pg_restore -d awx
```

If restoring into a fresh database:

```bash
createdb awx
zstd -dc awx.dump.zst | pg_restore -d awx
```

## Compression Method Comparison

| Method                | Compression Ratio |    CPU Impact | Restore / Decompress Speed | Best Use Case             |
| --------------------- | ----------------: | ------------: | -------------------------: | ------------------------- |
| `lz4`                 |               Low |      Very low |                  Very fast | Lowest CPU impact         |
| `gzip -1` / `pigz -1` |        Reasonable |  Low / medium |                   Moderate | Compatibility             |
| `zstd -1`             |              Good |           Low |                  Very fast | Busy database host        |
| `zstd -3`             |              Good |  Low / medium |                  Very fast | Recommended default       |
| `zstd -5`             |            Better |        Medium |                  Very fast | Storage-conscious backups |
| `gzip -6`             |        Reasonable | Medium / high |                     Slower | Legacy compatibility      |
| `xz`                  |         Very high |     Very high |                       Slow | Usually not recommended   |

## Suggested Profiles

### Balanced Production Default

Use this for most AAP/AWX environments:

```bash
pg_dump -Fc -Z0 awx \
  | nice -n 10 ionice -c2 -n7 zstd -3 -T2 \
  > awx_$(date +%F).dump.zst
```

### Lowest CPU Impact

Use this when the PostgreSQL host is already busy and CPU impact must be kept as low as possible:

```bash
pg_dump -Fc -Z0 awx \
  | nice -n 15 ionice -c2 -n7 zstd -1 -T1 \
  > awx_$(date +%F).dump.zst
```

### Better Compression

Use this when storage is more important than backup CPU usage:

```bash
pg_dump -Fc -Z0 awx \
  | nice -n 10 ionice -c2 -n7 zstd -5 -T2 \
  > awx_$(date +%F).dump.zst
```

### Very Low CPU with Larger Files

Use `lz4` when speed and low CPU impact matter more than storage size:

```bash
pg_dump -Fc -Z0 awx \
  | nice -n 15 ionice -c2 -n7 lz4 -1 \
  > awx_$(date +%F).dump.lz4
```

Restore with:

```bash
lz4 -dc awx.dump.lz4 | pg_restore -d awx
```

## Why Not Use `xz`?

`xz` can produce small backup files, but it usually has a poor trade-off for database backups:

* High CPU usage
* Slow compression
* Slow decompression
* Longer restore time
* Higher operational risk during incidents

For AAP/AWX backups, fast and reliable restore is usually more important than achieving the absolute smallest backup file.

## Why Not Use High zstd Levels?

Higher zstd levels can improve compression, but above around level `5` the extra gain is often small compared with the additional CPU cost.

Recommended range:

```text
zstd -1   lowest CPU
zstd -3   balanced default
zstd -5   better compression
```

Avoid high levels such as:

```bash
zstd -15
zstd -19
```

unless storage pressure is extreme and the backup runs on a non-production host.

## Threading Guidance

Avoid this on a production database host:

```bash
zstd -T0
```

`-T0` allows zstd to use all available CPU cores.

Prefer explicit limits:

```bash
zstd -1 -T1
zstd -3 -T2
zstd -5 -T2
```

Suggested thread counts:

| Host Type                 |         Recommended Threads |
| ------------------------- | --------------------------: |
| Busy production DB node   |                       `-T1` |
| Normal production DB node |                       `-T2` |
| Backup/offload host       | `-T0` or higher fixed value |
| Small VM                  |                       `-T1` |

## Native PostgreSQL Compression Notes

Depending on PostgreSQL version, some compression methods may be available directly in PostgreSQL tools.

However, for operational control, this pattern is often easier to manage:

```bash
pg_dump -Fc -Z0 awx | zstd -3 -T2 > awx.dump.zst
```

Benefits of external compression:

* Easier to tune CPU usage
* Easier to apply `nice` and `ionice`
* Easier to change compression method
* Easier to monitor separately
* Consistent behaviour across backup scripts

## Recommended Final Choice

For most AWX / AAP PostgreSQL backups:

```bash
zstd -3 -T2
```

Full command:

```bash
pg_dump -Fc -Z0 awx \
  | nice -n 10 ionice -c2 -n7 zstd -3 -T2 \
  > awx_$(date +%F).dump.zst
```

For a very busy host:

```bash
pg_dump -Fc -Z0 awx \
  | nice -n 15 ionice -c2 -n7 zstd -1 -T1 \
  > awx_$(date +%F).dump.zst
```

For better compression where CPU impact is acceptable:

```bash
pg_dump -Fc -Z0 awx \
  | nice -n 10 ionice -c2 -n7 zstd -5 -T2 \
  > awx_$(date +%F).dump.zst
```

## Summary

Use `zstd` rather than `gzip` or `xz` for most AAP/AWX PostgreSQL backups.

Best overall default:

```bash
zstd -3 -T2
```

Best low-impact setting:

```bash
zstd -1 -T1
```

Best storage-conscious setting:

```bash
zstd -5 -T2
```

Avoid `xz` unless the smallest possible backup size is more important than CPU usage and restore speed.
