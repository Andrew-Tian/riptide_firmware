onCopro = False
try:
	import socket
	from time import sleep
	import halSimulated
	import traceback
	import asyncio
except:
	onCopro = True
	import hal
	import usocket as socket
	import uasyncio as asyncio

import sys
import commands
import select

print('Setting up socket...')
incomingConnection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
incomingConnection.bind(('', 50000))
incomingConnection.listen(5)
connections = [incomingConnection]
connectionsBuffers = [[]]
print('Listening for connections...')


def dropConnection(s):
	s.close()
	connectionIndex = connections.index(s)
	del connectionsBuffers[connectionIndex]
	connections.remove(s)
	print("Lost connection")

def processIncomingData(s):
	if s == incomingConnection:
		conn, addr = incomingConnection.accept()
		print("Connected to "+str(addr))
		connections.append(conn)
		connectionsBuffers.append([])
	else:
		try:
			data = s.recv(50)
		except:
			dropConnection(s)
			return
		if not data:
			dropConnection(s)
			return

		connectionIndex = connections.index(s)

		# Command structure: Length, Command, Args...
		# Response structure: Length, values
		# Below code allows for multiple or partial commands to be received
		if not onCopro and sys.version_info < (3, 0):
			data = list(map(ord, data))
		inputBuffer = connectionsBuffers[connectionIndex]
		inputBuffer += data

		# While there is a whole command in the buffer
		while len(inputBuffer) > 0 and inputBuffer[0] <= len(inputBuffer):
			command = inputBuffer[1 : inputBuffer[0]]

			# Act on the command. Terminate connection on command length of 0
			if inputBuffer[0] == 0:
				print('Terminating a connection')
				connections.remove(s)
				s.close()
				# Remove the command from the buffer
				inputBuffer = inputBuffer[1:]
			else:
				response = commands.runCommand(command)
				response = [len(response) + 1] + response
				try:
					s.send(bytearray(response))
				except:
					dropConnection(s)
					return

				# Remove the command from the buffer
				inputBuffer = inputBuffer[inputBuffer[0]:]

		connectionsBuffers[connectionIndex] = inputBuffer


async def mainLoop():
	try:
		while True:
			readable, _, _ = select.select(connections, [], connections, 0)

			for s in readable:
				processIncomingData(s)

			if not onCopro:
				sleep(0.01)
			else:
				await asyncio.sleep(0)
	except Exception as exc:
		if not onCopro:
			traceback.print_exc()
			print(exc)
		else:
			sys.print_exception(exc)
		for s in connections:
			s.close()

async def depthLoop():
	await asyncio.sleep(1.0)
	if (hal.Depth.initialized):
		print("Zeroing depth")
		for i in range(1, 20):
			await hal.Depth.read()
		for i in range(1, 20):
			await hal.Depth.zeroDepth()
		print("Collecting depth")
		while True:
			try:
				await hal.Depth.read()
			except Exception as e:
				print("Depth error: " + str(e))
				await asyncio.sleep_ms(50)


async def lowVolt():
	while hal.BB.portVolt.value() < 18.5 or hal.BB.stbdVolt.value() < 18.5:
		await asyncio.sleep(1.0)
	while True:
		await asyncio.sleep(1.0)
		if hal.BB.portVolt.value() < 18.5 or hal.BB.stbdVolt.value() < 18.5:
			hal.ESC.stopThrusters()
			hal.blueLed.on()
			print("Low Battery")



if onCopro:
	loop = asyncio.get_event_loop()
	loop.create_task(depthLoop())
	loop.create_task(mainLoop())
	loop.create_task(lowVolt())
	loop.run_forever()
	loop.close()
else:
	loop = asyncio.get_event_loop()
	loop.run_until_complete(mainLoop())
	loop.close()
