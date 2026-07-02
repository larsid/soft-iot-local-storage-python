import os
import time
import requests
import csv
from datetime import datetime
from fogbed import FogbedExperiment, Container, setLogLevel

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, '../../'))

setLogLevel('info')

# ========================================================================
# FUNÇÃO DE EXTRAÇÃO AUTOMÁTICA DE DADOS (PROMETHEUS)
# ========================================================================
def exportar_dados_prometheus(start_time, end_time):
    print("\n[EXTRAÇÃO] Conectando ao Prometheus para salvar CPU e RAM...")
    url = 'http://localhost:9090/api/v1/query_range'
    
    # As queries buscam métricas apenas dos containers que começam com "mn." (Fogbed)
    queries = {
        'cpu_usage.csv': 'rate(container_cpu_usage_seconds_total{name=~"mn.*"}[1m])',
        'ram_usage_bytes.csv': 'container_memory_usage_bytes{name=~"mn.*"}'
    }
    
    os.makedirs('resultados_experimento', exist_ok=True)
    
    for filename, query in queries.items():
        params = {
            'query': query,
            'start': start_time,
            'end': end_time,
            'step': '15s' # Coleta 1 ponto de dado a cada 15 segundos
        }
        try:
            response = requests.get(url, params=params)
            data = response.json()
            
            filepath = os.path.join('resultados_experimento', filename)
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['Container', 'Timestamp', 'Value'])
                
                if data['status'] == 'success':
                    for result in data['data']['result']:
                        container_name = result['metric'].get('name', 'unknown')
                        for value in result['values']:
                            # Converte o timestamp Unix para data legível
                            dt_str = datetime.fromtimestamp(value[0]).strftime('%Y-%m-%d %H:%M:%S')
                            val = value[1]
                            writer.writerow([container_name, dt_str, val])
            print(f"✅ Dados salvos com sucesso: {filepath}")
        except Exception as e:
            print(f"❌ Erro ao exportar {filename}: {e}")


# ========================================================================
# 1. SETUP DE VARIÁVEIS E PORTAS 
# ========================================================================
NODE_ID = 1
HOST_ZATO_PORT = 11220 + NODE_ID
HOST_MQTT_PORT = 1880 + NODE_ID
HOST_MQTT_WS_PORT = 9000 + NODE_ID
HOST_ADMIN_PORT = 8180 + NODE_ID
HOST_ADMIN_PORT_SSL = 8181 + NODE_ID
HOST_SSH_PORT = 22020 + NODE_ID

container_name = f'zato-{NODE_ID}'

os.makedirs('config/auto-generated', exist_ok=True)
with open('config/auto-generated/env.ini', 'w') as f:
    f.write("[env]\n")
    f.write("My_API_Password_1=senha123\n") 
    f.write("My_API_Password_2=senha123\n")
    f.write("Zato_Project_Root=/opt/hot-deploy/myproject\n")

# ========================================================================
# 2. CONFIGURAÇÃO DA TOPOLOGIA FOGBED
# ========================================================================
exp = FogbedExperiment(metrics_enabled=True)
cloud = exp.add_virtual_instance('cloud')

zato_esb = Container(
    name=container_name,
    ip='10.0.0.10',
    user='root',
    privileged=True,
    dimage='rhianpablo11/zato-base-congelada:v5',
    dcmd='/usr/local/bin/start_wrapper.sh',    
    environment={
        'Zato_Dashboard_Password': '123456',
        'ZATO_SSH_PASSWORD': '123456',
        'Zato_IDE_Password': '123456',
        'Zato_Log_Env_Details': 'true',
        'Zato_Build_Verbosity': '',
        'Zato_SAVE_DATA_ENABLED': 'True',
        'Zato_COLLECTION_TIME': '2',
        'Zato_PUBLISH_TIME': '6',
        'Zato_AGGREGATION_WINDOW_MINUTES': '10',
        'Zato_DATA_RETENTION_SECONDS': '1200',
        'Zato_TANGLE_API_IP': '10.0.0.10', 
        'Zato_TANGLE_API_PORT': '3001',
        'Zato_ZMQ_IP': '10.0.0.10',
        'Zato_ZMQ_PORT': '5556',
        'Zato_GATEWAY_REAL_IP': '10.0.0.14',
        'Zato_Workers': '1',
        'Zato_Start_Web_Admin': 'False',
        'Zato_Start_Load_Balancer': 'True',
        'Zato_Start_File_Listener': 'False',
        'Zato_Start_Queue_Bridge': 'False',
        'Zato_MQTT_USER': 'meu_usuario_iot',
        'Zato_MQTT_PASS': 'minha_senha_super_segura'
    },
    port_bindings={
        22: HOST_SSH_PORT,
        8183: HOST_ADMIN_PORT,
        8184: HOST_ADMIN_PORT_SSL,
        11223: HOST_ZATO_PORT, 
        11225: 11225,
        3000: 3030,
        15672: 15672,
        1883: HOST_MQTT_PORT,
        9001: HOST_MQTT_WS_PORT
    }
)

NUM_EDGES = 4
edges = []

# Criamos 4 switches separados e já ligamos todos eles na Nuvem
for i in range(NUM_EDGES):
    edge_inst = exp.add_virtual_instance(f'edge_{i}')
    edges.append(edge_inst)
    exp.add_link(edge_inst, cloud)

exp.add_docker(zato_esb, cloud)

NUM_DEVICES = 100
devices = []
print(f"Criando {NUM_DEVICES} dispositivos virtuais distribuídos em {NUM_EDGES} antenas...")

for i in range(1, NUM_DEVICES + 1):
    ip_suffix = 10 + i 
    device_ip = f'10.0.0.{ip_suffix}'
    device_name = f'device-{i}'
    device_id = f'py_device_{i:02d}' 
    
    # 1º: Distribuição de Carga - O device escolhe uma antena (0, 1, 2, 3...)
    edge_alvo = edges[i % NUM_EDGES]
    
    
    tempo_espera = 180 + (i * 2) 
    dev = Container(
        name=device_name,
        ip=device_ip, 
        dimage='virtual-fot-device-python:v5',
        dcmd=f'bash -c "sleep 180 && python -u main.py"',
        environment={
            'DEVICE_ID': device_id,
            'BROKER_IP': '10.0.0.10', 
            'PORT': 1883,
            'USERNAME': 'meu_usuario_iot',
            'PASSWORD': 'minha_senha_super_segura',
            'BIND_IP': device_ip,
            'CONNECTION_TIMEOUT': 0,
            'ENABLE_LATENCY_TRACKER': 'False',
            'LATENCY_API_URL': 'http://10.0.0.5:8080/api/latency-records/records'
        }
    )
    # 2º: Injeta o container especificamente na antena que separamos para ele
    exp.add_docker(dev, edge_alvo)
    devices.append(dev)

try:
    print(f"Iniciando topologia e o container {container_name}...")
    exp.start()

    print("Criando diretórios isolados dentro do container...")
    zato_esb.cmd('mkdir -p /opt/hot-deploy/myproject /opt/hot-deploy/enmasse /opt/hot-deploy/python-reqs /home/ubuntu/mapping_archives/devices_config/')

    print("Criando snapshot dos arquivos locais (docker cp)...")
    real_docker_name = f"mn.{container_name}"

    os.system(f"docker cp {PROJECT_ROOT}/. {real_docker_name}:/opt/hot-deploy/myproject/")
    os.system(f"docker cp {PROJECT_ROOT}/config/enmasse/enmasse.yaml {real_docker_name}:/opt/hot-deploy/enmasse/enmasse.yaml")
    os.system(f"docker cp {PROJECT_ROOT}/config/auto-generated/env.ini {real_docker_name}:/opt/hot-deploy/enmasse/env.ini")
    os.system(f"docker cp {PROJECT_ROOT}/config/python-reqs/requirements.txt {real_docker_name}:/opt/hot-deploy/python-reqs/requirements.txt")
    os.system(f"docker cp {PROJECT_ROOT}/impl/src/archives/. {real_docker_name}:/home/ubuntu/mapping_archives/devices_config/")
    os.system(f"docker exec {real_docker_name} rm -f /opt/hot-deploy/myproject/impl/scripts/fogbed-test.py")
    
    print("Ajustando permissões de arquivos para o usuário Zato...")
    os.system(f"docker exec {real_docker_name} chown -R zato:zato /home/ubuntu/")
    os.system(f"docker exec {real_docker_name} chown -R zato:zato /opt/hot-deploy/")

    print("✅ Container configurado e arquivos copiados!")
    print(f"O Dashboard Admin está rodando em http://localhost:{HOST_ADMIN_PORT}")
    
    # ====================================================================
    # 5. CRONÔMETRO DO EXPERIMENTO E ENCERRAMENTO AUTOMÁTICO
    # ====================================================================
    TEMPO_MINUTOS = 10
    TEMPO_SEGUNDOS = TEMPO_MINUTOS * 60
    
    start_timestamp = int(time.time())
    
    print(f"\n🚀 O experimento vai rodar automaticamente por {TEMPO_MINUTOS} minuto(s). Pode ir tomar um café!")
    
    # Loop que imprime o status a cada 5 minutos
    for restante in range(TEMPO_SEGUNDOS, 0, -300):
        print(f"⏱️  Tempo restante: {restante / 60:.1f} minutos...")
        time.sleep(min(300, restante))
        
    end_timestamp = int(time.time())
    
    print("\n🛑 Tempo esgotado! Iniciando o desligamento...")
    exportar_dados_prometheus(start_timestamp, end_timestamp)
    
except Exception as ex: 
    print(f"Erro: {ex}")
finally:
    exp.stop()
    print("🏁 Topologia destruída com segurança.")