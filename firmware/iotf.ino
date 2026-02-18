#include <Wire.h>
#include "DHT.h"

// ---------- PIN CONFIG ----------
#define DHTPIN            15
#define DHTTYPE           DHT22
#define SOIL_PIN          34
#define FLAME_PIN         35
#define IR_PIN            32
#define RELAY_PIN_FAN     14 //IN1
#define RELAY_PIN_PUMP    27 //IN4
#define RELAY_PIN_LIGHT   26 //IN2 
#define RELAY_PIN_BUZZER  25 //IN3

const bool RELAY_ACTIVE_LOW = false;

// ---------- DEFAULT THRESHOLDS ----------
int TEMP_ON   = 28;
int TEMP_OFF  = 25;
int SOIL_DRY_THRESHOLD = 1800;  // Higher = Dry
int LUX_DARK = 5;
int LUX_BRIGHT = 20;

DHT dht(DHTPIN, DHTTYPE);

// ---------- AUTOMATION ----------
bool automationEnabled = true;

// ---------- SENSOR ENABLE FLAGS ----------
bool enableTemp = true;
bool enableHumidity = true;
bool enableSoil = true;
bool enableLight = true;
bool enableFlame = true;
bool enableIR = true;

// ---------- FUNCTIONS ----------
void setRelay(int pin, bool on) {
  digitalWrite(pin, on ? HIGH : LOW);
}

float readBH1750() {
  Wire.beginTransmission(0x23);
  Wire.write(0x10);
  if (Wire.endTransmission() != 0) return -1;
  delay(120);
  Wire.requestFrom(0x23, 2);
  if (Wire.available() < 2) return -2;
  uint16_t raw = (Wire.read() << 8) | Wire.read();
  return (float)raw / 1.2;
}

// ---------- SETUP ----------
void setup() {
  Serial.begin(115200);
  dht.begin();
  Wire.begin(21, 22);

  pinMode(RELAY_PIN_FAN, OUTPUT);
  pinMode(RELAY_PIN_PUMP, OUTPUT);
  pinMode(RELAY_PIN_LIGHT, OUTPUT);
  pinMode(RELAY_PIN_BUZZER, OUTPUT);

  pinMode(FLAME_PIN, INPUT);
  pinMode(IR_PIN, INPUT);

  setRelay(RELAY_PIN_FAN, false);
  setRelay(RELAY_PIN_PUMP, false);
  setRelay(RELAY_PIN_LIGHT, false);
  setRelay(RELAY_PIN_BUZZER, false);

  Serial.println("✅ Greenhouse controller started");
  Serial.println("Automation: ON");
}

// ---------- LOOP ----------
void loop() {
  // --- SERIAL COMMANDS ---
  while (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    if (cmd.length() == 0) continue;

    char c = cmd.charAt(0);

    // Relay controls
    switch(c) {
      case 'F': setRelay(RELAY_PIN_FAN, true); break;
      case 'f': setRelay(RELAY_PIN_FAN, false); break;
      case 'P': setRelay(RELAY_PIN_PUMP, true); break;
      case 'p': setRelay(RELAY_PIN_PUMP, false); break;
      case 'L': setRelay(RELAY_PIN_LIGHT, true); break;
      case 'l': setRelay(RELAY_PIN_LIGHT, false); break;
      case 'B': setRelay(RELAY_PIN_BUZZER, true); break;
      case 'b': setRelay(RELAY_PIN_BUZZER, false); break;

      // Automation toggle
      case 'A': automationEnabled = true; Serial.println("Automation: ON"); break;
      case 'a': automationEnabled = false; Serial.println("Automation: OFF"); break;

      // Sensor sensitivity sliders
      case 'S':
        if (cmd.length() > 2) {
          char param = cmd.charAt(1);
          int value = cmd.substring(2).toInt();
          switch(param){
            case 'T': TEMP_ON = value; break;
            case 'S': SOIL_DRY_THRESHOLD = value; break;
            case 'L': LUX_DARK = value; break;
          }
        }
        break;

      // Sensor enable/disable
      case 'X':
        if (cmd.length() > 2){
          char s = cmd.charAt(1);
          int val = cmd.charAt(2) - '0';
          switch(s){
            case 'T': enableTemp = val; break;
            case 'H': enableHumidity = val; break;
            case 'S': enableSoil = val; break;
            case 'L': enableLight = val; break;
            case 'F': enableFlame = val; break;
            case 'I': enableIR = val; break;
          }
        }
        break;
    }
  }

  // --- AUTOMATION ---
  if (automationEnabled){
    float t = dht.readTemperature();
    float h = dht.readHumidity();
    int soilValue = analogRead(SOIL_PIN);
    float lux = readBH1750();
    int flameVal = digitalRead(FLAME_PIN);
    int irVal = digitalRead(IR_PIN);

    if(enableTemp && !isnan(t)){
      if(t >= TEMP_ON) setRelay(RELAY_PIN_FAN, true);
      else if(t <= TEMP_OFF) setRelay(RELAY_PIN_FAN, false);
    }

    // ✅ REVERSED SOIL LOGIC
    if(enableSoil){
      if(soilValue > SOIL_DRY_THRESHOLD) {
        setRelay(RELAY_PIN_PUMP, true);   // Dry soil → Pump ON
      } else {
        setRelay(RELAY_PIN_PUMP, false);  // Wet soil → Pump OFF
      }
    }

    if(enableLight && lux>=0){
      if(lux < LUX_DARK) setRelay(RELAY_PIN_LIGHT,true);
      else if(lux > LUX_BRIGHT) setRelay(RELAY_PIN_LIGHT,false);
    }

    if((enableFlame && flameVal==LOW) || (enableIR && irVal==LOW)){
      setRelay(RELAY_PIN_BUZZER,true);
    }else{
      setRelay(RELAY_PIN_BUZZER,false);
    }
  }

  // --- SEND SENSOR DATA ---
  float t = dht.readTemperature();
  float h = dht.readHumidity();

  if(enableTemp && !isnan(t)){
      Serial.printf("🌡 Temp: %.2f °C\n", t);
  }

  if(enableHumidity && !isnan(h)){
      Serial.printf("💧 Hum: %.2f %%\n", h);
  }

  if(enableSoil) {
    int soilValue = analogRead(SOIL_PIN);
    Serial.printf("🌱 Soil ADC: %d\n", soilValue);
  }

  if(enableLight){
      float lux = readBH1750();
      if(lux>=0) Serial.printf("💡 Light: %.2f lux\n", lux);
  }
  if(enableFlame || enableIR) Serial.printf("🔥 Flame: %d  👀 IR: %d\n", digitalRead(FLAME_PIN), digitalRead(IR_PIN));

  Serial.printf("RelayStates:%d %d %d %d\n", digitalRead(RELAY_PIN_FAN),
                digitalRead(RELAY_PIN_PUMP), digitalRead(RELAY_PIN_LIGHT),
                digitalRead(RELAY_PIN_BUZZER));

  delay(1000);
}
