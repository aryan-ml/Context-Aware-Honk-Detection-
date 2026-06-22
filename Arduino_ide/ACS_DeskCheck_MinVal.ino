const int CURRENT_SENSOR_PIN = 34;

void setup() {
  Serial.begin(115200);
}

void loop() {

  int rawADC = analogRead(CURRENT_SENSOR_PIN);

  bool hornActive = false;

  if(rawADC < 2699)
  {
    hornActive = true;
  }

  Serial.print("ADC: ");
  Serial.print(rawADC);

  Serial.print("  Horn: ");

  if(hornActive)
    Serial.println("TRUE");
  else
    Serial.println("FALSE");

  delay(100);
}