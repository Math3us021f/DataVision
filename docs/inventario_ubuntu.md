# Inventário do Ubuntu Server (SOMENTE LEITURA)

> Parte da Etapa 12 (ver [etapa12_validacao_mvp.md](etapa12_validacao_mvp.md)). **Todos os comandos abaixo apenas leem informação**: não instalam, não removem, não reiniciam nada e não alteram arquivos. Rode-os por SSH no servidor e cole as saídas na conversa.
>
> **Antes de colar**: remova senhas, tokens, chaves e qualquer valor de variável de ambiente. Os comandos foram escolhidos para não imprimi-los (por exemplo, o `docker inspect` abaixo usa campos específicos e **não** mostra `Env`).
>
> Quem executa é você (a aplicação e o Claude Code não se conectam ao servidor). Se algum comando pedir `sudo`, ele é só para ler (`ss`, `ufw status`).

## 1. Sistema e recursos

```bash
lsb_release -a
uname -r
uptime
timedatectl | head -n 5
free -h
nproc
df -h
```

## 2. Rede e firewall

```bash
ip -br addr
ip route
sudo ss -tlnp
sudo ufw status verbose
```

O que importa: quais portas estão em escuta e em **qual endereço** (`0.0.0.0` = todas as interfaces; `192.168.x.x` = só aquela), e se o firewall está ativo.

## 3. SSH (só as diretivas relevantes, sem chaves)

```bash
sudo grep -hE '^\s*(Port|PermitRootLogin|PasswordAuthentication|PubkeyAuthentication)\b' /etc/ssh/sshd_config /etc/ssh/sshd_config.d/*.conf 2>/dev/null
```

## 4. Docker

```bash
docker --version
docker info --format 'Rootless={{.SecurityOptions}} Driver={{.Driver}} Containers={{.Containers}}'
docker ps -a --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'
docker images --digests
docker volume ls
docker network ls
cat /etc/docker/daemon.json
```

## 5. MinIO existente (sem expor segredos)

```bash
# política de reinício, portas publicadas e montagens — NÃO imprime Env
docker inspect minio-server --format 'restart={{.HostConfig.RestartPolicy.Name}} ports={{json .HostConfig.PortBindings}} mounts={{json .Mounts}} user={{.Config.User}} privileged={{.HostConfig.Privileged}}'

# saúde da API
curl -sI http://127.0.0.1:9000/minio/health/live | head -n 1

# dados no disco
ls -ld ~/minio/data
du -sh ~/minio/data

# últimas linhas do log (confira se não há segredos antes de colar)
docker logs --tail 20 minio-server
```

Para os **nomes dos buckets** existentes, abra o console do MinIO no navegador e anote só os nomes (sem abrir o conteúdo). Não use as credenciais em nenhum comando colado aqui.

## 6. Python, backups e atualizações

```bash
python3.13 --version
crontab -l 2>/dev/null
systemctl list-timers --all --no-pager | head -n 15
systemctl is-enabled unattended-upgrades 2>/dev/null
apt list --upgradable 2>/dev/null | head -n 15
```

## 7. VM (no Windows, PowerShell) — para planejar a reversão

```powershell
VBoxManage list vms
VBoxManage showvminfo "Servidor-Python" --machinereadable | Select-String 'memory|cpus|nic|SnapshotName'
VBoxManage snapshot "Servidor-Python" list
```

## O que vou procurar nas saídas

- Portas expostas em `0.0.0.0` que deveriam estar só na interface host-only.
- Firewall inativo ou com regras amplas.
- SSH aceitando senha e/ou login de root.
- MinIO: imagem sem digest, rodando com usuário root do MinIO no uso da aplicação, política de reinício, onde ficam os dados.
- Espaço em disco e memória para a aplicação + Postgres.
- Existência (ou não) de backup, snapshots da VM e atualizações pendentes.
