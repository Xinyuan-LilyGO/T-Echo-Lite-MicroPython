<h1 align = "center">T-Echo-Lite-MicroPython</h1>

<p align="center" width="100%">
    <img src="image/3.jpg" alt="">
</p>

## **English | [中文](./README_CN.md)**

## Version iteration:
| Version                              | Update date                       |
| :-------------------------------: | :-------------------------------: |
| T-Echo-Lite_V1.0            | 2024-12-06                         |
| T-Echo-Lite-Kit_V1.0            | 2025-10-14                         |

## PurchaseLink
| Product                     | SOC           |  FLASH  |  PSRAM   | Link                   |
| :------------------------: | :-----------: |:-------: | :---------: | :------------------: |
| T-Echo-Lite_V1.0   | nRF52840 |   1M   |256kB| [LILYGO Mall](https://lilygo.cc/products/t-echo-lite?_pos=1&_sid=79b4c08e7&_ss=r&variant=45331277906101) |
| T-Echo-Lite-Kit_V1.0   |  |  || NULL |

## Directory
- [Describe](#describe)
- [Preview](#preview)
- [Module](#module)
- [SoftwareDeployment](#SoftwareDeployment)
- [PinOverview](#pinoverview)
- [RelatedTests](#RelatedTests)
- [FAQ](#faq)
- [Project](#project)

## Describe

T-Echo-Lite is a lightweight version based on T-Echo, featuring a smaller volume and lower power consumption design compared to T-Echo. Its minimum deep sleep power consumption can reach 2μA to 10μA (due to differences in onboard components on different boards, power consumption performance may vary; the minimum power consumption mentioned here is based on the engineering board tested by the LILYGO laboratory). The board is equipped with a rich set of features, including an inertial sensor, LORA module, solar charging function (5V), external GPS, and more. Its excellent power consumption performance allows T-Echo-Lite to achieve superior battery life.

T-Echo-Lite-Kit is a baseboard expansion for T-Echo-Lite, primarily extending peripherals such as a keyboard, speaker, microphone, and vibration motor.

> [!NOTE]
> T-Echo-Lite-Kit and T-Echo-Lite-KeyShield refer to the same product. The legacy name is retained only in existing file and directory names.

> [!IMPORTANT]
> Important note: The L76K module and the ICM20948 module are external expansion modules. The default purchase link does not include these two modules (the ICM20948 module is connected via soldering, while the L76K module is connected via pin headers). They need to be purchased separately.

## Preview

### Actual Product Image

<p align="center" width="100%">
    <img src="image/1.jpg" alt="">
</p>

---

<p align="center" width="100%">
    <img src="image/2.jpg" alt="">
</p>

---

<p align="center" width="100%">
    <img src="image/3.jpg" alt="">
</p>

## Module

### T-Echo-Lite Section
### 1. MCU
*   Chip: nRF52840
*   RAM: 256kB
*   FLASH: 1M
*   Related Documentation:
    > [nRF52840_Datasheet](https://docs.nordicsemi.com/bundle/ps_nrf52840/page/keyfeatures_html5.html)

### 2. Screen
* Name: GDEM0122T61

* Size: 1.22 inches

* Resolution: 176x192px

* Screen Type: E-PAPER

* Driver Chip: SSD1681

* Bus Communication Protocol: IIC

* Additional Notes: Fast refresh is not supported (after consulting the screen manufacturer, they replied that it is not supported), it is recommended to use full refresh only

*   Related Documentation:
    > [GDEM0122T61](./information/GDEM0122T61.pdf)  
    > [SSD1681](./information/SSD1681.pdf)  

### 3. LORA
* Chip Module: S62F

* Chip: SX1262

* Bus Communication Protocol: SPI

*   Related Documentation:
    > [S62F](./information/S62F.pdf)  
    > [S62F Application Note](./information/S62F_ApplicationNote_Ver_D.pdf)

#### S62F Hardware Configuration

* RF switch: T-Echo-Lite uses AcSiP control mode A. The nRF52840 drives `RF_VC1` (`P0.27`) and `RF_VC2` (`P1.01`) directly. `DIO2` (`P0.05`) is routed separately and is not hardwired to the RF switch on this board. Set `RF_VC1/RF_VC2` to `HIGH/LOW` for transmit and `LOW/HIGH` for receive.
* TCXO: The embedded 32 MHz TCXO is controlled internally by SX1262 `DIO3`. Set `tcxoVoltage` explicitly to `3.0 V` when initializing the radio.
* Regulator: `VREG` and `DCC_SW` are connected through a 15 uH inductor. Use the DC-DC regulator mode (`useRegulatorLDO = false`).

### 4. GPS
* Chip Module: L76K

* Bus Communication Protocol: UART

*   Related Documentation:
    > [L76KB-A58](./information/L76KB-A58.pdf)  

> [!IMPORTANT]
> Important note: The L76K module is an external expansion module. The default purchase link does not include this module, so it needs to be purchased separately.

### 5. Inertial Measurement Unit
* Chip: ICM20948

* Bus Communication Protocol: IIC

*   Related Documentation:
    > [ICM20948](./information/ICM20948.pdf)  

> [!IMPORTANT]
> Important note: The ICM20948 module is an external expansion module. The default purchase link does not include this module, so it needs to be purchased separately.

### 6. Flash
* Chip: ZD25WQ32C or ZD25Q32D

* Bus Communication Protocol: SPI

*   Related Documentation:
    > [ZD25WQ32CEIGR](./information/ZD25WQ32CEIGR.pdf)
    >[ZD25Q32DTIGT](./information/ZD25Q32DTIGT.pdf)

### T-Echo-Lite-Kit Section
### 1. Keyboard Backlight

* Driver Chip: AW21009QNR

* Bus Communication Protocol: IIC

* Related Information:
    >[AW21009QNR](./information/AW21009QNR.pdf)

### 2. Vibration

* Driver Chip: AW86224

* Bus Communication Protocol: IIC

* Related Information:
    >[AW86224AFCR](./information/AW86224AFCR.pdf)

### 3. Speaker Microphone

* Driver Chip: ES8311

* Bus Communication Protocols: IIC, IIS

* Related Information:
    >[ES8311](./information/ES8311.pdf)

### 4. Keyboard

* Driver Chip: TCA8418

* Bus Communication Protocol: IIC

* Related Information:
    >[tca8418](./information/tca8418.pdf)

## SoftwareDeployment

### Examples Support

### T-Echo-Lite Examples
| Example | Support | Description | Picture |
| ------  | ------  | ------ | ------ |
| [Battery_Measurement](./examples/T-Echo-Lite/Battery_Measurement) | <p align="center">![alt text][supported]  |  |  |
| [BLE_Uart](./examples/T-Echo-Lite/BLE_Uart) | <p align="center">![alt text][supported]  |  |  |
| [Button_Triggered](./examples/T-Echo-Lite/Button_Triggered) | <p align="center">![alt text][supported]  |  |  |
| [Display](./examples/T-Echo-Lite/Display) | <p align="center">![alt text][supported]  |  |  |
| [Display_BLE_Uart](./examples/T-Echo-Lite/Display_BLE_Uart) | <p align="center">![alt text][supported]  |  |  |
| [Display_SX1262](./examples/T-Echo-Lite/Display_SX1262) | <p align="center">![alt text][supported]  |  |  |
| [Flash](./examples/T-Echo-Lite/Flash) | <p align="center">![alt text][supported]  |  |  |
| [Flash_Erase](./examples/T-Echo-Lite/Flash_Erase) | <p align="center">![alt text][supported]  |  |  |
| [Flash_Speed_Test](./examples/T-Echo-Lite/Flash_Speed_Test) | <p align="center">![alt text][supported]  |  |  |
| [GPS](./examples/T-Echo-Lite/GPS) | <p align="center">![alt text][supported]  |  |  |
| [GPS_Full](./examples/T-Echo-Lite/GPS_Full) | <p align="center">![alt text][supported]  |  |  |
| [ICM20948](./examples/T-Echo-Lite/ICM20948) | <p align="center">![alt text][supported]  |  |  |
| [IIC_Scan_2](./examples/T-Echo-Lite/IIC_Scan_2) | <p align="center">![alt text][supported]  |  |  |
| [nrf52840_module](./examples/T-Echo-Lite/nrf52840_module) | <p align="center">![alt text][supported]  |  |  |
| [Original_Test](./examples/T-Echo-Lite/Original_Test) |<p align="center">![alt text][supported]  | factory original testing |  |
| [Sleep_Wake_Up](./examples/T-Echo-Lite/Sleep_Wake_Up) | <p align="center">![alt text][supported]  |  |  |
| [SX126x_PingPong](./examples/T-Echo-Lite/SX126x_PingPong) | <p align="center">![alt text][supported]  |  |  |
| [SX126x_PingPong_2](./examples/T-Echo-Lite/SX126x_PingPong_2) | <p align="center">![alt text][supported]  |  |  |
| [sx126x_tx_continuous_wave](./examples/T-Echo-Lite/sx126x_tx_continuous_wave) | <p align="center">![alt text][supported]  |  |  |

### T-Echo-Lite-Kit Examples
| Example | Support | Description | Picture |
| ------  | ------  | ------ | ------ |
| [aw21009qnr](./examples/T-Echo-Lite-KeyShield/aw21009qnr) | <p align="center">![alt text][supported]  |  |  |
| [aw86224](./examples/T-Echo-Lite-KeyShield/aw86224) | <p align="center">![alt text][supported]  |  |  |
| [es8311](./examples/T-Echo-Lite-KeyShield/es8311) | <p align="center">![alt text][supported]  |  |  |
| [general_test](./examples/T-Echo-Lite-KeyShield/general_test) | <p align="center">![alt text][supported]  | Product factory original testing  |  |
| [tca8418](./examples/T-Echo-Lite-KeyShield/tca8418) | <p align="center">![alt text][supported]  |  |  |
| [speaker_certification](./examples/T-Echo-Lite-KeyShield/speaker_certification) | <p align="center">![alt text][supported]  |  |  |

[supported]: https://img.shields.io/badge/-supported-green "example"

| Bootloader | Description | Picture |
| ------  | ------  | ------ |
| [bootloader](./bootloader/) | |  |

| Firmware | Description | Picture |
| ------  | ------  | ------ |
| [T-Echo-Lite-MicroPython-1.0.0-20260831](./firmware/) |  |  |

### IDE and Flashing

#### 1.Thonny IDE

1. Install [Thonny IDE]([Thonny, Python IDE for beginners](https://thonny.org/)) 

2. Download version 4.1.7 or the latest version (Choose Linux or macOS or Windows)

   ![thonny1](image\thonny1.png)

3. After installing the installation package, open Thonny IDE

4. Click Configure interpreter

   ![thonny2](image\thonny2.png)

5. Select MicroPython (generic)

   ![thonny3](image\thonny3.png)

6. Select the corresponding port number and confirm

   ![thonny4](image\thonny4.png)

7. Test run the program (Print "hello world" below is OK. You can use the shortcut key F5 to run the program and ctrl+F2 to end it)

   `print("hello world")`

   ![thonny5](image\thonny5.png)

8. If you want to run the program automatically, please click Save, then select MicroPython device and name it main.py

   ![thonny6](image\thonny6.png)

   ![thonny7](image\thonny7.png)

9. After successful saving, reset the T-Echo-Lite.

#### 2.Arduino lab for micropython IDE

1. Install [Arduino lab for micropython IDE](https://labs.arduino.cc/en/labs/micropython).

2. Install **Desktop Version (Choose Linux or macOS or Windows)**

3. Open the folder and open "Arduino Lab for MicroPython.exe".

   ![Arduino1](image\Arduino1.png)

4. Connect the serial port.

   ![Arduino2](image\Arduino2.png)

5. Click Run the program (If you want to Stop the program, please click Stop).

   ![Arduino3](image\Arduino3.png)

6. If you want to run the program automatically, please click file and then create a new code named "main.py". Select  "Board" Then write the code into main.py and save it. Reset the T-Echo-Lite.

   ![Arduino4](image\Arduino4.png)

#### 3.RT-Thread MicroPython

1. Install [Python](https://www.python.org/downloads/) (according to you to download the corresponding operating system version, suggest to download version 3.7 or later), MicroPython requirement 3. X version, if you have already installed, you can skip this step).
2. Install [Visual Studio Code](https://code.visualstudio.com/Download), Choose installation based on your system type.
3. Open the "Extension" section of the Visual Studio Code software sidebar(Alternatively, use "<kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>X</kbd>" to open the extension),Search for the "RT-Thread MicroPython" extension and download it.
4. During the installation of the extension, you can go to GitHub to download the program. You can download the main branch by clicking on the "<> Code" with green text, or you can download the program versions from the "Releases" section in the sidebar.
5. After the installation of the extension is completed, open the Explorer in the sidebar(Alternatively, use "<kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>E</kbd>" go open it),Click on "Open Folder," locate the project code you just downloaded (the entire folder), and click "Add." At this point, the project files will be added to your workspace.
6. Click on "<kbd>[Device Connected/Disconnected](./image/vscode1.png)</kbd>" at the lower left corner, and then click on the pop-up window "<kbd>[COMX](./image/vscode2.png)</kbd>" at the top to connect the serial port. A pop-up pops up at the lower right corner saying "<kbd>[Connection successful](./image/vscode3.png)</kbd>" and the connection is complete.
7. After opening the code, click on“<kbd>[▶](./image/vscode4.png)</kbd>”at the lower left corner to run the program“<kbd>[Run this MicroPython file directly on the device](./image/vscode5.png)</kbd>”，Or use the<kbd>Alt</kbd>+<kbd>Q</kbd>），if you want to stop the program, click on the lower left corner of the“<kbd>[⏹](./image/vscode6.png.png)</kbd>”stop running the program.**(If you need to run the program automatically on the board, please copy the code to the "[main.py](../examples/main.py)" file under the "exampels" folder and save it. Select the "main.py" file with the left mouse button. Right-click the mouse and select "[Download this file/folder to device](./image/vscode7.png)", then press the reset button on the board to run the program automatically.)**

#### JLINK Flashing Firmware and Bootloader

1.  Install the software [nRF-Connect-for-Desktop](https://www.nordicsemi.com/Products/Development-tools/nRF-Connect-for-Desktop/Download#infotabs)

2.  Install the software [JLINK](https://www.segger.com/downloads/jlink/)

3.  Connect the JLINK pins correctly as shown in the figure below

<p align="center" width="100%">
    <img src="image/12.jpg" alt="">
</p>

4.  Open the software nRF-Connect-for-Desktop and install the tool [Programmer](./image/10.png) and open it

5.  Add files, select both the bootloader file and the firmware file at the same time, click [Erase&write](./image/11.png), and the flashing will be completed.

## PinOverview

For pin definitions, please refer to the configuration file: 
<br />

[t_echo_lite_config.py](./libraries/t_echo_lite_config.py)  

## FAQ

* Q. Why does my board fail to flash when I use USB directly?
* A. Please press and release the RST chip reset button, wait for LED1 to light up (you must wait for LED1 to light up), then press and release the RST button again. Observe that LED1 gradually dims and then gradually lights up, indicating that the boot download mode has been entered. At this point, you can flash the board.

<br />

* Q. How should the Bluetooth antenna and Lora antenna of the T-Echo-Lite module be distinguished?
* A. The Bluetooth antenna and Lora antenna of the T-Echo-Lite module are as shown in the following figure:

<p align="center" width="100%">
    <img src="image/14.png" alt="">
</p>

<br />



## Project
* [T-Echo-Lite_V1.0](./project/T-Echo-Lite_V1.0)
* [T-Echo-Lite-Kit_V1.0](./project/T-Echo-Lite-KeyShield_V1.0)
