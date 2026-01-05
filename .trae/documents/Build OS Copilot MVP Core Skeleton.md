# OS Copilot MVP Implementation Plan

This plan outlines the steps to build the Minimum Viable Product (MVP) for the "OS Copilot" desktop agent as requested.

## 1. Project Initialization & Dependencies
- Create `requirements.txt` containing necessary Python libraries:
    - `openai`: For communicating with GPT-4o.
    - `pyautogui`: For screen capture and mouse control.
    - `Pillow`: For image processing.
    - `pydantic`: For data validation (optional but good for JSON parsing, will stick to standard lib `json` for simplicity if preferred, or `openai`'s structured output).

## 2. Configuration Module
- Create `config.py` to manage settings:
    - `OPENAI_API_KEY`: Placeholder for the user's API key.
    - `SCREEN_SCALING`: Screen DPI scaling factor (default 1.0).
    - `API_MODEL`: Default to "gpt-4o".

## 3. Core Logic Implementation (`main.py`)
- **Imports & Setup**: Initialize OpenAI client using config.
- **`capture_screen_base64()`**: 
    - Use `pyautogui.screenshot()` to grab the screen.
    - Convert the image to JPEG format in memory.
    - Encode to Base64 string for API transmission.
- **`ask_vlm_for_action(instruction, image_base64)`**:
    - Construct the prompt for GPT-4o.
    - **System Prompt**: Define the persona (GUI Automation Expert) and output format (JSON).
    - **User Message**: Combine the text instruction and the base64 image.
    - **API Call**: Send request to OpenAI.
    - **Response Handling**: Parse the JSON response to extract `x`, `y` coordinates and the `reason`.
- **`main()` Function**:
    - Implement the linear test flow: Capture -> Ask -> Move.
    - Add error handling for API failures or parsing issues.
    - Use `pyautogui.moveTo()` to verify coordinates visually without clicking (safety mode).

## 4. Verification
- The user will need to provide their OpenAI API Key in `config.py`.
- Run `main.py` to test the "Observe -> Think -> Act" loop.
