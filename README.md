# Log Viewer
This tool allows users to analyze Telnet logs efficiently. It provides features such as filtering and highlighting specific log entries.

## Notes
- Closing a browser does not disconnect the Telnet session.
- To properly close a Telnet session, use the "Disconnect" button in the web interface.
- The app may show up as "Not Responding" on macOS due to the way it handles Telnet connections. This is a known issue and does not affect functionality.
- The app supports up to 1,000,000 log entries.
- The app was tested on M1 using Chrome and Safari browsers.

## Features
- Regex pattern matching
- Customizable highlighting colors
- Import/export filters
- Monitor log using different filter sets (one per browser tab)

## Build Instructions
1. Activate a virtual environment built with python3.11
   ```bash
   source venv_python3.11/bin/activate
   ```
2. Install dependencies if not already installed:
   ```bash
   pip install flask telnetlib3 py2app
   ```
3. Build the application:
   ```bash
   python3.11 setup.py py2app
   ```
4. The built application will be located in the `dist` directory.

## Running the App on macOS
- Double-click the application
- If "unidentified developer" warning appears
   - Right-click the app and select "Open". 
- If app does not open
  - Go to System Settings > Privacy & Security
  - Scroll down to Security section
  - Under "Allow apps downloaded from:", click "Open Anyway" for the Log Viewer app