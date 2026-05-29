# Pi-DCC Wiring Diagram & GPIO Pinout

## Raspberry Pi 4B GPIO Header (40-pin)

```
                    3.3V [1 ] [2 ] 5V
        I2C SDA (GPIO 2) [3 ] [4 ] 5V
        I2C SCL (GPIO 3) [5 ] [6 ] GND
                          [7 ] [8 ]
                      GND [9 ] [10]
          Relay (GPIO 17) [11] [12] GPIO 18 ← NeoPixel Data
                          [13] [14] GND
   Button: Lathe (GPIO 22) [15] [16] GPIO 23 ← Button: Floor Sweep
                     3.3V [17] [18] GPIO 24 ← Button: Assembly Table 1
                          [19] [20] GND
                          [21] [22] GPIO 25 ← Button: Assembly Table 2
                          [23] [24]
                      GND [25] [26]
                          [27] [28]
                          [29] [30] GND
                          [31] [32] GPIO 12 (test servo PWM)
                          [33] [34] GND
                          [35] [36]
                          [37] [38]
                      GND [39] [40]
```

---

## GPIO Assignments

| GPIO | Physical Pin | Function | Connection |
|------|-------------|----------|------------|
| 2    | 3           | I2C SDA  | PCA9685 SDA, ADS1115 SDA |
| 3    | 5           | I2C SCL  | PCA9685 SCL, ADS1115 SCL |
| 17   | 11          | Relay    | Relay module IN (dust collector on/off) |
| 18   | 12          | NeoPixel | WS2812B data in (12 LEDs) |
| 22   | 15          | Button   | Lathe manual trigger (to GND) |
| 23   | 16          | Button   | Floor Sweep manual trigger (to GND) |
| 24   | 18          | Button   | Assembly Table 1 manual trigger (to GND) |
| 25   | 22          | Button   | Assembly Table 2 manual trigger (to GND) |

---

## Wiring Connections

### I2C Bus (shared by PCA9685 + ADS1115)

```
Pi Pin 3 (GPIO 2/SDA) ───────┬──── PCA9685 SDA ──── ADS1115 SDA
Pi Pin 5 (GPIO 3/SCL) ───────┬──── PCA9685 SCL ──── ADS1115 SCL
Pi Pin 1 (3.3V)       ───────┬──── PCA9685 VCC ──── ADS1115 VCC
Pi Pin 6 (GND)        ───────┬──── PCA9685 GND ──── ADS1115 GND
```

### PCA9685 Servo Driver (address 0x40)

```
PCA9685 V+ terminal ──── External 5V PSU (+)
PCA9685 GND terminal ─┬─ External 5V PSU (-)
                       └─ Pi GND (shared ground)

PCA9685 Channel 0  ──── Servo: gate_center_branch
PCA9685 Channel 1  ──── Servo: gate_table_saw_bottom
PCA9685 Channel 2  ──── Servo: gate_table_saw_guard
PCA9685 Channel 3  ──── Servo: gate_jointer
PCA9685 Channel 4  ──── Servo: gate_assembly_table1
PCA9685 Channel 5  ──── Servo: gate_bandsaw
PCA9685 Channel 6  ──── Servo: gate_router_table
PCA9685 Channel 7  ──── Servo: gate_planer
PCA9685 Channel 8  ──── Servo: gate_drum_sander
PCA9685 Channel 9  ──── Servo: gate_lathe
PCA9685 Channel 10 ──── Servo: gate_floor_sweep
PCA9685 Channel 11 ──── Servo: gate_assembly_table2
```

Each servo connector on the PCA9685: Signal, V+, GND (powered from V+ terminal)

### ADS1115 ADC (address 0x48)

```
ADS1115 ADDR ──── GND (sets address to 0x48)

ADS1115 A0 ──── CT Sensor: Table Saw
ADS1115 A1 ──── CT Sensor: Jointer
ADS1115 A2 ──── CT Sensor: Band Saw
ADS1115 A3 ──── CT Sensor: Router Table
```

For 6 tools, you need a **second ADS1115** (address 0x49):

```
ADS1115 #2 ADDR ──── VDD (sets address to 0x49)

ADS1115 #2 A0 ──── CT Sensor: Planer
ADS1115 #2 A1 ──── CT Sensor: Drum Sander
ADS1115 #2 A2 ──── (spare)
ADS1115 #2 A3 ──── (spare)
```

### CT Sensor Wiring (per sensor)

```
            ┌─────────────┐
AC Wire ════╪═ CT Clamp   ╪
            └──┬───────┬──┘
               │       │
          ┌────┴───────┴────┐
          │  Burden Resistor │  (e.g., 33Ω for SCT-013-000)
          │   (across CT)    │
          └────┬───────┬────┘
               │       │
               │    ┌──┴──┐
               │    │ R1  │ 10kΩ ──── 3.3V
               │    └──┬──┘
               │       ├──────────── ADS1115 Ax input
               │    ┌──┴──┐
               │    │ R2  │ 10kΩ ──── GND
               │    └──┬──┘
               └───────┘
```

The voltage divider (R1+R2) biases the CT output to 1.65V (mid-rail) so the AC waveform swings around center within the ADC's input range.

### Relay Module (Dust Collector)

```
Pi Pin 11 (GPIO 17) ──── Relay IN
Pi Pin 6  (GND)     ──── Relay GND
Pi Pin 2  (5V)      ──── Relay VCC  (or separate supply for high-current relay)

Relay NO ──── Dust collector power circuit
Relay COM ─── Dust collector power circuit
```

### NeoPixel LED Strip (12 LEDs)

```
Pi Pin 12 (GPIO 18) ──── NeoPixel Data In
Pi Pin 6  (GND)     ──── NeoPixel GND
External 5V         ──── NeoPixel VCC (5V, shared GND with Pi)
```

Note: Add a 300-500Ω resistor between GPIO 18 and NeoPixel Data In.
Add a 1000µF capacitor across NeoPixel VCC/GND for surge protection.

### Manual Trigger Buttons

```
GPIO 22 (pin 15) ──── Button ──── GND    (Lathe)
GPIO 23 (pin 16) ──── Button ──── GND    (Floor Sweep)
GPIO 24 (pin 18) ──── Button ──── GND    (Assembly Table 1)
GPIO 25 (pin 22) ──── Button ──── GND    (Assembly Table 2)
```

No external pull-up resistors needed — the Pi's internal pull-ups are enabled in software.

---

## Power Supply Summary

| Supply | Powers | Notes |
|--------|--------|-------|
| Pi 3.3V | I2C bus, ADS1115, PCA9685 logic | From Pi header pin 1 |
| Pi 5V | Relay module (optional) | From Pi header pin 2 |
| External 5V (high current) | 12 servos via PCA9685 V+ | ~2A per servo stall, size accordingly |
| External 5V | NeoPixel strip | ~60mA per LED × 12 = ~720mA max |
| Mains (via relay) | Dust collector | Relay rated for motor load |

**Important:** All GND connections must be tied together (Pi, external supplies, PCA9685, ADS1115, relay, NeoPixels).
