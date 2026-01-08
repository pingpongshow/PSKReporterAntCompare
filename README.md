# PSKReporterAntCompare
Compare up to 10 antenna configurations using ADIF files from PSKReporter

Tool to compare HF (or other) antennas from the same transmitter or receiver by analyzing FT8 reception reports from PSKReporter.

Basic steps:
  1) generate the data on PSK reporter by transmitting on the frequencies of interest on FT8 (transmit a FT8 CQ call)
  2) Download ADIF file from PSKReporter to your computer
  3) Run the docker container and go to web based interface
  4) upload ADIF files and compare.

This tool runs inside of a docker compose.


Detailed steps:
1) Configure your antenna design to be tested.
2) Transmit on FT8 by making CQ calls of the bands of interest, you can do all bands your transmitter is capable of if desired. Important each antenna design should be separated by transmitting the the callsign configuration of CALLSIGN\x, where x is a number from 0 to 9, representing a antenna configuration to be tested. I would recommend testing all configurations within a close timespan as possible to minimize changes due to atmospheric changes, unless that is what you are looking for.
     In my case, transmitting on FT8 a CG call with the call sign of KD2NDR\0 would be for testing antenna configuration #1, KD2NDR\1 would be to       test an additional design and so on. This tool only compares between 2 or more antenna configurations, up to 10 maximum.
3) Go to PSKReporter and search for your callsign \x (ie KD2NDR\0) and filter select FT8 and "sent by", you should see your reports, click "show logbook" and download the ADIF fianle. Do this for EACH of the \x antenna configurations tested.
4) Run the docker (you must have docker installed on your PC/Mac. Download the project files and unzip them somewhere easy to find. 
      Mac:
         Open terminal and cd into the folder containing the project files
         enter the command  "docker build -t adif-antenna-tool ."
         enter the command "docker run -p 5995:5995 adif-antenna-tool" after the previous step completes, it may take a few minutes.
         open your web browser and go to http://127.0.0.1:5995
     Windows:
       I dont have a windows PC, but steps should be similar
5) when on the web page, upload your ADIF files and click compare, enjoy the results


<img width="1438" height="894" alt="Screenshot 2026-01-07 at 4 03 34 PM" src="https://github.com/user-attachments/assets/9bfc7835-12cc-4f62-8619-462b4a4c5ff5" />

<img width="1373" height="873" alt="Screenshot 2026-01-07 at 4 02 20 PM" src="https://github.com/user-attachments/assets/043ab7d0-110e-4078-b9ff-00b631094a7d" />

<img width="1383" height="876" alt="Screenshot 2026-01-07 at 4 02 31 PM" src="https://github.com/user-attachments/assets/957c008a-aa5b-4d2a-9091-ce8dc73b046b" />

<img width="1375" height="838" alt="Screenshot 2026-01-07 at 4 02 41 PM" src="https://github.com/user-attachments/assets/578638ec-1be0-4abf-850d-f1d26ba66d86" />



