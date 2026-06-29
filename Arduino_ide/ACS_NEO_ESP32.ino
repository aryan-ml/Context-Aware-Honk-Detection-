// Listen at:
// mosquitto_sub -h localhost -t "car/telemetry/horn"
// Make sure to check the IP with tht host if error *rc-2* pops 
// Match IP with the given ip below and both should be exaclty same "hostname -I | cut -d ' ' -f 1"

#include <WiFi.h>
#include <PubSubClient.h>
#include <TinyGPSPlus.h>
#include <ArduinoJson.h>

// --- NETWORK CONFIGURATION ---
const char* ssid = "OnePlus 11R 5G";      // Change to your Wi-Fi SSID
const char* password = "HYPERLLM";        // Change to your Wi-Fi Password
const char* mqtt_ip = "10.253.208.224";    // Change to your Laptop's Local IP

// --- PIN DEFINITIONS ---
const int GPS_RX_PIN = 16;
const int GPS_TX_PIN = 17;
const int CURRENT_SENSOR_PIN = 34; // ACS712 OUT connected to GPIO 34

// --- OBJECT INITIALIZATION ---
WiFiClient espClient;
PubSubClient client(espClient);
TinyGPSPlus gps;

unsigned long lastPublishTime = 0;
const unsigned long publishInterval = 1000; // Broadcast updates every 1 seconds


void setup_wifi() {
  delay(10);
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
  }
}

void reconnect_mqtt() {
  while (!client.connected()) {
    if (client.connect("ESP32_Vehicle_Node")) {
      Serial.println("MQTT Synchronized.");
    } else {
      delay(5000);
    }
  }
}

void setup() {
  Serial.begin(115200);
  Serial2.begin(9600, SERIAL_8N1, GPS_RX_PIN, GPS_TX_PIN);
  pinMode(CURRENT_SENSOR_PIN, INPUT);
  
  setup_wifi();
  client.setServer(mqtt_ip, 1883);
}

void loop() {
  while (Serial2.available() > 0) {
    gps.encode(Serial2.read());
  }

  if (!client.connected()) {
    reconnect_mqtt();
  }
  client.loop();

  unsigned long now = millis();
  if (now - lastPublishTime > publishInterval) {
    lastPublishTime = now;

    // 1. Read Current Sensor Volts
    int rawADC = analogRead(CURRENT_SENSOR_PIN);

    const int HORN_THRESHOLD = 2690;

    // 3. Horn Flag Logic (If current threshold crossed, set to true)
    bool hornActive = (rawADC < HORN_THRESHOLD);


    Serial.println("-------------------------");
    Serial.print("Latitude : ");
    Serial.println(gps.location.lat(), 6);

    Serial.print("Longitude: ");
    Serial.println(gps.location.lng(), 6);

    Serial.print("ADC      : ");
    Serial.println(rawADC);

    Serial.print("Horn     : ");
    Serial.println(hornActive ? "YES" : "NO");

    Serial.println("-------------------------");
    
    if (gps.location.isValid()) {
      StaticJsonDocument<256> doc;
      
      doc["timestamp"]       = millis();
      doc["car_id"]          = "CAR_001";
      doc["lat"]             = gps.location.lat();
      doc["lon"]             = gps.location.lng();
      doc["horn"]            = hornActive;
      

      char jsonBuffer[256];
      serializeJson(doc, jsonBuffer);

      client.publish("car/telemetry/horn", jsonBuffer);
    }
  }
}
