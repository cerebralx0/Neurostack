from devices.muse import Muse

muse = Muse()
muse.connect()
muse.start()

# connect neurostack server
muse.neurostack_connect('35.222.93.233', 8001)

# run client as server as well (to allow API for front end)
muse.initialize_handlers()
muse.app.run(host='localhost', port=8001)
