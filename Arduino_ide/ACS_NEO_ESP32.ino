// Listen at:
// mosquitto_sub -h localhost -t "car/telemetry/horn"
// Make sure to check the IP with tht host if error *rc-2* pops 

#include <WiFi.h>
#include <PubSubClient.h>
#include <TinyGPSPlus.h>
#include <ArduinoJson.h>

// --- NETWORK CONFIGURATION ---
const char* ssid = "OnePlus 11R 5G";      // Change to your Wi-Fi SSID
const char* password = "HYPERLLM";        // Change to your Wi-Fi Password
const char* mqtt_ip = "10.136.71.224";    // Change to your Laptop's Local IP

// --- PIN DEFINITIONS ---
const int GPS_RX_PIN = 16;
const int GPS_TX_PIN = 17;
const int CURRENT_SENSOR_PIN = 34; // ACS712 OUT connected to GPIO 34

// --- OBJECT INITIALIZATION ---
WiFiClient espClient;
PubSubClient client(espClient);
TinyGPSPlus gps;

unsigned long lastPublishTime = 0;
const unsigned long publishInterval = 2000; // Broadcast updates every 2 seconds

// --- CALIBRATION VARIABLES ---
const float SENSITIVITY = 0.100; // 100mV per Amp for the 20A module
const float Q_VREF = 2.50;       // Midpoint voltage baseline for 0 Amperes

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
    float pinVoltage = (rawADC / 4095.0) * 3.3; // Convert 12-bit ADC to ESP32 pin voltage
    
    // 2. Calculate Amps (Since we are on a desk, we look for deviation from baseline)
    // Note: Due to resistor tolerances, baseline might read slightly off 2.5V.
    float currentAmps = (pinVoltage - 1.65) / SENSITIVITY; // Adjusted for ESP32 3.3V attenuation scale

    // 3. Horn Flag Logic (If current threshold crossed, set to true)
    bool hornActive = false;
    
    // DESK TESTING TRICK: Since nothing is plugged in, touching the ACS712 chip 
    // with your bare finger introduces electromagnetic noise that will cause 
    // the ADC to spike up. We use that noise to test our logic flag!
    
    if (rawADC < 2690) {  // Custom threshold for ACS 30A clocking at 2699 with touch and idle at around 27xx 
      hornActive = true;  // For demo desk purpose only with finger
    }



    if (gps.location.isValid()) {
      StaticJsonDocument<256> doc;
      
      doc["timestamp"]       = "2026-06-22T00:45:00"; 
      doc["lat"]             = gps.location.lat();
      doc["lon"]             = gps.location.lng();
      doc["horn"]            = hornActive; 
      doc["inside_geofence"] = false; 

      char jsonBuffer[256];
      serializeJson(doc, jsonBuffer);

      client.publish("car/telemetry/horn", jsonBuffer);
    }
  }
}
