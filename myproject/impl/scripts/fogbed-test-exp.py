import os
from fogbed import FogbedExperiment, Container, setLogLevel

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, '../../'))

setLogLevel('info')

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

# ========================================================================
# 2. GERAÇÃO DO ARQUIVO ENV.INI (Traduzido dos 'echo' do Bash)
# ========================================================================
os.makedirs('config/auto-generated', exist_ok=True)
with open('config/auto-generated/env.ini', 'w') as f:
    f.write("[env]\n")
    f.write("My_API_Password_1=senha123\n") 
    f.write("My_API_Password_2=senha123\n")
    f.write("Zato_Project_Root=/opt/hot-deploy/myproject\n")

# ========================================================================
# 3. CONFIGURAÇÃO DA TOPOLOGIA FOGBED
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
        
        # =======================================================
        #  VARIÁVEIS DE OTIMIZAÇÃO DE RAM
        # =======================================================
        'Zato_Workers': '1',
        'Zato_Start_Web_Admin': 'False',
        'Zato_Start_Load_Balancer': 'False',
        'Zato_Start_File_Listener': 'False',
        'Zato_Start_Queue_Bridge': 'False',
        'Zato_MQTT_USER': 'meu_usuario_iot',
        'Zato_MQTT_PASS': 'minha_senha_super_segura'
    },
    port_bindings={
        22: HOST_SSH_PORT,
        8183: HOST_ADMIN_PORT,
        8184: HOST_ADMIN_PORT_SSL,
        # A porta 11223 (LB) morreu - Caso o load balancer esteja desativado. Mapea-se a 17010 (Server1):
        11223: HOST_ZATO_PORT, 
        11225: 11225,
        3000: 3030,
        15672: 15672,
        1883: HOST_MQTT_PORT,
        9001: HOST_MQTT_WS_PORT
    }
)


# 1. Cria a camada de Borda
edge = exp.add_virtual_instance('edge')

# ========================================================================
# INSTANCIANDO MÚLTIPLOS DISPOSITIVOS COM UM LOOP FOR
# ========================================================================
NUM_DEVICES = 5
devices = []

print(f"Criando {NUM_DEVICES} dispositivos virtuais...")

# 2. Configuração do FoT Device
for i in range(1, NUM_DEVICES + 1):
    # Calculo do IP dinâmico (começando do 10.0.0.11)
    ip_suffix = 10 + i 
    device_ip = f'10.0.0.{ip_suffix}'
    device_name = f'device-{i}'
    device_id = f'py_device_{i:02d}' # Formata para py_device_01, py_device_02...

    # Cria o container do dispositivo
    dev = Container(
        name=device_name,
        ip=device_ip, 
        dimage='rhianpablo11/virtual-fot-device-python:v5',
        dcmd=f'bash -c "sleep 0 && python -u main.py"',
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
    
    # Adiciona o dispositivo criado à instância da Borda (edge)
    exp.add_docker(dev, edge)
    devices.append(dev)


exp.add_docker(zato_esb, cloud)
exp.add_link(edge, cloud)

try:
    print(f"Iniciando topologia e o container {container_name}...")
    exp.start()

    # ====================================================================
    # 4. EXECUTANDO MKDIR E DOCKER CP
    # ====================================================================
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
    
    input("\nPressione ENTER para encerrar o Fogbed e destruir a rede...\n")
    
except Exception as ex: 
    print(f"Erro: {ex}")
finally:
    exp.stop()