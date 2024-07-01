from ReadWriteMemory import ReadWriteMemory, ReadWriteMemoryError, os

DEBUG = False

# marker in openGOAL memory to search for
MARKER_BYTES = b'UnLiStEdStRaTs_JaK2\x00'

class OpenGoalAutoTracker(object):

  def __init__(self):
    self.status = 'wakeup'
    self.process = None
    self.marker_addr = None

  def connect(self):
    try:
      self.status = 'connected'
      self.process = ReadWriteMemory().get_process_by_name('gk')
      return True
    except ReadWriteMemoryError as e:
      self.status = 'no_gk'
      self.process = None
      return False

  def find_markers(self, close_process: bool) -> bool:
    try:
      if self.process is None and not self.connect():
        return False

      # find marker in process memory
      self.process.open()

      tmp_marker_addr = None

      # try any previously saved marker_addr
      if self.marker_addr is not None:
        # verify marker_addr
        tmp_bytes = self.process.readByte(self.marker_addr, 20)

        if tmp_bytes == MARKER_BYTES:
          # reuse marker_addr
          tmp_marker_addr = self.marker_addr

          if DEBUG:
            print(f'reusing marker at address: {self.marker_addr}')

      # no saved+verified marker_addr, need to search
      if tmp_marker_addr is None:
        # only need to search through first module
        modules = self.process.get_modules()
        mem_start = modules[0]
        mem_end = modules[1]

        tmp = mem_start
        while tmp < mem_end:
          # save some time by checking only first byte initially
          first_byte = self.process.readByte(tmp, 1)

          if first_byte == b'U':
            # first byte matched, check the full 20 bytes
            tmp_bytes = self.process.readByte(tmp, 20)

            if tmp_bytes == MARKER_BYTES:
              # found it!
              tmp_marker_addr = tmp
              # also persist it for next time
              self.marker_addr = tmp

              if DEBUG:
                print(f'found marker at address: {tmp}')
              break

          # start from next byte
          tmp += 1

      # if still not marker_addr, something went wrong
      if tmp_marker_addr is None:
        self.status = 'no_marker'
        print(f'Couldn''t find base address for {MARKER_BYTES}!')
        return False

      self.status = 'marker'

      # The address of the GOAL struct is stored in a u64 next to the marker!
      # 20 bytes for 'UnLiStEdStRaTs_JaK1 ' | 4 bytes padding | 8 bytes (u64) for GOAL struct address
      #   so GOAL struct address is 24 = 0x18 bytes from base_ptr
      goal_struct_addr_ptr = tmp_marker_addr + 24
      self.goal_struct_addr = int.from_bytes(self.process.readByte(goal_struct_addr_ptr, 8), byteorder='little', signed=False)
      if DEBUG:
        print(f'found goal_struct_addr as: {self.goal_struct_addr}')

      if close_process:
        self.process.close()

      return True
    except Exception as e:
      print(f'Encountered exception {e}')
      self.status = 'no_gk'
      self.process = None
      return False


  def check_orbcount_file(self, arg1):
      desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
      file_path = os.path.join(desktop_path, "jak2_orbcount.txt")
      initial_orbcount = "0000/3125 Orbs"

      # Check if the file exists
      if not os.path.exists(file_path):
          # Create the file with initial content if it doesn't exist
          with open(file_path, "w") as file:
              file.write(initial_orbcount)
          print(f"File created with initial content: {initial_orbcount}")
      else:
          # Read the existing file
          with open(file_path, "r") as file:
              content = file.read().strip()

          # Get the current number of orbs
          current_orbs = content.split("/")[0].strip()
          num_orbs = arg1

          # Update the file if the number of orbs is different
          if current_orbs != num_orbs:
              new_content = f"{num_orbs}/3125 Orbs"
              with open(file_path, "w") as file:
                  file.write(new_content)
              #print(f"File updated to: {new_content}")
          else:
              print("No update needed. The number of orbs is the same.")


  def read_field_values(self, fields):
    try:
      if not self.find_markers(False):
        print(f'Error finding markers in memory')
        self.process.close()
        return None

      field_values = {}

      for key in fields:
        if 'skip' in fields[key] and fields[key]['skip'] == True:
          continue

        field_values[key] = int.from_bytes(self.process.readByte(self.goal_struct_addr + fields[key]['offset'], fields[key]['length']), byteorder='little', signed=False)

      if DEBUG:
        print(f'field_values: {field_values}')

      # calculate completion_percent if all necessary fields are found
      if 'num_orbs' in field_values:
        self.check_orbcount_file(field_values['num_orbs'])
      self.process.close()

      return field_values
    except Exception as e:
      print(f'Encountered exception {e}')
      self.status = 'no_gk'
      self.process = None
      return None