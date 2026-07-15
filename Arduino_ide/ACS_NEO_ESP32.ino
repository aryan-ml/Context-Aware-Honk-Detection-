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
const char* mqtt_ip = "10.181.118.224";    // Change to your Laptop's Local IP

// --- PIN DEFINITIONS ---
const int GPS_RX_PIN = 16;
const int GPS_TX_PIN = 17;
const int CURRENT_SENSOR_PIN = 34; // ACS712 OUT connected to GPIO 34

// --- GPS FILTERING ---
const float HDOP_THRESHOLD = 6.0;     // skip fix if HDOP exceeds this
const int GPS_WINDOW_SIZE = 5;         // ring buffer entries for position averaging
const char* CAR_ID = "CAR_001";         // vehicle identifier

// --- OBJECT INITIALIZATION ---
WiFiClient espClient;
PubSubClient client(espClient);
TinyGPSPlus gps;

unsigned long lastPublishTime = 0;
const unsigned long publishInterval = 1000; // Broadcast updates every 1 seconds

// --- GPS RING BUFFER ---
struct {
  double lats[GPS_WINDOW_SIZE];
  double lngs[GPS_WINDOW_SIZE];
  int index = 0;
  int count = 0;
} gpsBuffer;



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

double computeCentroid(double arr[], int count) {
  double sum = 0.0;
  for (int i = 0; i < count; i++) {
    sum += arr[i];
  }
  return sum / count;
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

    // Skip this fix if HDOP is too high (unreliable position)
    if (gps.hdop.isValid() && gps.hdop.hdop() > HDOP_THRESHOLD) {
      Serial.println("Skipped: HDOP too high");
      return;
    }

    // Only accept valid GPS fixes into the buffer
    if (!gps.location.isValid()) {
      Serial.println("Skipped: no GPS fix");
      return;
    }

    // Add to ring buffer
    gpsBuffer.lats[gpsBuffer.index] = gps.location.lat();
    gpsBuffer.lngs[gpsBuffer.index] = gps.location.lng();
    gpsBuffer.index = (gpsBuffer.index + 1) % GPS_WINDOW_SIZE;
    if (gpsBuffer.count < GPS_WINDOW_SIZE) {
      gpsBuffer.count++;
    }

    // Don't publish until buffer is full
    if (gpsBuffer.count < GPS_WINDOW_SIZE) {
      Serial.print("Buffering GPS: ");
      Serial.print(gpsBuffer.count);
      Serial.print(" / ");
      Serial.println(GPS_WINDOW_SIZE);
      return;
    }

    // Compute centroid
    double avgLat = computeCentroid(gpsBuffer.lats, GPS_WINDOW_SIZE);
    double avgLng = computeCentroid(gpsBuffer.lngs, GPS_WINDOW_SIZE);

    // 1. Read Current Sensor Volts
    int rawADC = analogRead(CURRENT_SENSOR_PIN);

    // TODO: Calibrate HORN_THRESHOLD using actual vehicle horn.
    const int HORN_THRESHOLD = 2690;

    // 3. Horn Flag Logic (If current threshold crossed, set to true)
    bool hornActive = (rawADC < HORN_THRESHOLD);

    Serial.println("-------------------------");
    Serial.print("Latitude : ");
    Serial.println(avgLat, 6);

    Serial.print("Longitude: ");
    Serial.println(avgLng, 6);

    Serial.print("ADC      : ");
    Serial.println(rawADC);

    Serial.print("Horn     : ");
    Serial.println(hornActive ? "YES" : "NO");

    Serial.print("HDOP     : ");
    Serial.println(gps.hdop.hdop());

    Serial.print("Sats     : ");
    Serial.println(gps.satellites.value());

    Serial.println("-------------------------");
    
    StaticJsonDocument<256> doc;
    
    doc["timestamp"]       = millis();
    doc["car_id"]          = CAR_ID;
    doc["lat"]             = avgLat;
    doc["lon"]             = avgLng;
    doc["horn"]            = hornActive;
    doc["hdop"]            = gps.hdop.hdop();
    doc["satellites"]      = gps.satellites.value();
    doc["adc"]             = rawADC;
    doc["gps_age"]         = gps.location.age();
    doc["gps_valid"]       = gps.location.isValid();

    char jsonBuffer[256];
    serializeJson(doc, jsonBuffer);

    if (client.publish("car/telemetry/horn", jsonBuffer)) {
      Serial.println("Published:");
      Serial.println(jsonBuffer);
      Serial.print("Packet Size: ");
      Serial.println(strlen(jsonBuffer));
    } else {
      Serial.println("Publish Failed");
    }
  }
}