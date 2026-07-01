# -*- coding: utf-8 -*-

from zato.server.service import Service
import sqlite3
import os

# Caminho do banco de dados (mesmo usado pelo storage)
DB_FILENAME = "/opt/zato/env/soft_iot_data.db"

class BaseAPIService(Service):
    """ Classe base para conexao com banco e formatação """
    
    def _get_conn(self):
        if not os.path.exists(DB_FILENAME):
            raise ValueError(f"Banco de dados não encontrado em {DB_FILENAME}")
        
        conn = sqlite3.connect(DB_FILENAME)
        conn.row_factory = sqlite3.Row # Permite acessar colunas por nome
        return conn

    def _format_rows(self, cursor):
        """ Converte linhas do SQLite para lista de dicionários """
        results = []
        for row in cursor.fetchall():
            results.append(dict(row))
        return results

class GetLastSensorData(BaseAPIService):
    """
    Retorna o último dado registrado para um sensor específico.
    Equivalente Java: getLastSensorData(Device device, Sensor sensor)
    """
    name = 'soft-iot.api.get-last-data'

    def handle(self):
        self.logger.info("Processando requisição GetLastSensorData")
        self.logger.info(f"Payload recebido: {self.request.payload}")
        self.logger.info(f"Tipo do payload recebido: {type(self.request.payload)}")
        device_id = self.request.payload.get('device_id')
        sensor_id = self.request.payload.get('sensor_id')

        if not device_id or not sensor_id:
            self.response.payload = {'error': 'device_id and sensor_id are required'}
            self.response.status_code = 400
            return

        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            
            query = """
                SELECT * FROM sensor_data 
                WHERE device_id = ? AND sensor_id = ?
                ORDER BY start_datetime DESC 
                LIMIT 1
            """
            cursor.execute(query, (device_id, sensor_id))
            data = self._format_rows(cursor)
            
            self.response.payload = {'data': data[0] if data else None}
            
        except Exception as e:
            self.logger.error(f"Erro na API GetLastSensorData: {e}")
            self.response.payload = {'error': str(e)}
            self.response.status_code = 500
        finally:
            if 'conn' in locals(): conn.close()

class GetSensorHistory(BaseAPIService):
    """
    Retorna histórico de dados com filtros opcionais de data.
    Equivalente Java: getSensorDataByDateTime e getSensorData
    """
    name = 'soft-iot.api.get-history'

    def handle(self):
        
        device_id = self.request.payload.get('device_id')
        sensor_id = self.request.payload.get('sensor_id')
        start_date = self.request.payload.get('start_date') # Esperado formato ISO ou timestamp
        end_date = self.request.payload.get('end_date')
        limit = self.request.payload.get('limit', 100)

        if not device_id or not sensor_id:
            self.response.payload = {'error': 'device_id and sensor_id are required'}
            self.response.status_code = 400
            return

        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            
            # Construção dinâmica da query
            query = "SELECT * FROM sensor_data WHERE device_id = ? AND sensor_id = ?"
            params = [device_id, sensor_id]

            if start_date:
                query += " AND start_datetime >= ?"
                params.append(start_date)
            
            if end_date:
                query += " AND end_datetime <= ?"
                params.append(end_date)

            query += " ORDER BY start_datetime DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)
            data = self._format_rows(cursor)
            
            self.response.payload = {'count': len(data), 'data': data}
            
        except Exception as e:
            self.logger.error(f"Erro na API GetSensorHistory: {e}")
            self.response.payload = {'error': str(e)}
            self.response.status_code = 500
        finally:
            if 'conn' in locals(): conn.close()


class GetSensorLastAggregatedData(BaseAPIService):
    """
    Retorna o conjunto de dados que foi agregado relacionado àquele sensor
    Equivalente Java: getLastAggregatedSensorData(device, sensor)
    """

    name = 'soft-iot.api.get-sensor-last-aggregated-data'

    def handle(self):
        device_id = self.request.payload.get('device_id')
        sensor_id = self.request.payload.get('sensor_id')

        if not device_id or not sensor_id:
            self.respose.payload = {'error': 'device_id and sensor_id are required'}
            self.response.status_code = 400
            return
        
        try:
            conn = self._get_conn()
            cursor = conn.cursor()

            query = "SELECT * FROM sensor_data WHERE device_id = ? AND sensor_id = ? AND aggregation_status = ? ORDER BY start_datetime DESC LIMIT 1"
            params = [device_id, sensor_id, 1]

            cursor.execute(query, params)
            data = self._format_rows(cursor)

            self.response.payload = {'data': data[0] if data else None}

        except Exception as e:
            self.logger.error(f"Erro na API GetSensorLastAggregatedData: {e}")
            self.response.payload = {'error': str(e)}
            self.response.status_code = 500
        finally:
            if 'conn' in locals(): conn.close()


class GetSensorAggregatedData(BaseAPIService):
    """
    Retorna o conjunto de dados que foi agregado relacionado àquele sensor
    Equivalente Java: getAggregatedSensorData(device, sensor)
    """

    name = 'soft-iot.api.get-sensor-aggregated-data'

    def handle(self):
        device_id = self.request.payload.get('device_id')
        sensor_id = self.request.payload.get('sensor_id')

        if not device_id or not sensor_id:
            self.response.payload = {'error': 'device_id and sensor_id are required'}
            self.response.status_code = 400
            return
        
        try:
            conn = self._get_conn()
            cursor = conn.cursor()

            query = "SELECT * FROM sensor_data WHERE device_id = ? AND sensor_id = ? AND aggregation_status = ? ORDER BY start_datetime ASC"
            params = [device_id, sensor_id, 1]

            cursor.execute(query, params)
            data = self._format_rows(cursor)

            self.response.payload = {'data': data[0] if data else None}

        except Exception as e:
            self.logger.error(f"Erro na API GetSensorAggregatedData: {e}")
            self.response.payload = {'error': str(e)}
            self.response.status_code = 500
        finally:
            if 'conn' in locals(): conn.close()