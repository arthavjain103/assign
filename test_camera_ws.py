#!/usr/bin/env python
import asyncio
import websockets
import json

async def test_camera_ws():
    uri = 'ws://localhost:8000/ws/camera/CAM_1'
    try:
        async with websockets.connect(uri) as websocket:
            print(f'✓ Connected to {uri}')
            # Receive first frame
            msg = await asyncio.wait_for(websocket.recv(), timeout=5)
            data = json.loads(msg)
            print(f'Received message type: {data.get("type")}')
            print(f'Camera ID: {data.get("camera_id")}')
            print(f'Frame number: {data.get("frame_number")}')
            print(f'Data length: {len(data.get("data", ""))}')
    except Exception as e:
        print(f'Error: {e}')

asyncio.run(test_camera_ws())
