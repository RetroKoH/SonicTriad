#######################
# Decompression class #
#######################

class Decompress:
	input = None
	position = 0
	bit = 0
	output = []

	#######################################
	# Open file                           #
	#######################################
	# ARGUMENTS:                          #
	#    filename - Filename              #
	# RETURNS:                            #
	#    True if successful, false if not #
	#######################################

	def open_file(self, filename):
		self.input = None
		self.position = 0
		self.bit = 0
		try:
			with open(filename, "rb") as file:
				self.input = file.read()
		except IOError as e:
			print(e)
			return False
		return True

	######################################
	# Set input data                     #
	######################################
	# ARGUMENTS:                         #
	#     data - Input data              #
	#     position - Input data position #
	######################################

	def set_input(self, data, position = 0):
		self.input = data
		self.position = position
		self.bit = 0

	######################
	# Reset bit position #
	######################

	def reset_bit(self):
		if self.bit > 0:
			self.bit = 0
			self.position += 1

	########################
	# Read byte            #
	########################
	# ARGUMENTS:           #
	#     peek - Peek flag #
	# RETURNS:             #
	#     Read value       #
	########################

	def read_byte(self, peek = False):
		if not self.input:
			raise IndexError("No data to read byte from.")

		if self.position >= len(self.input):
			raise IndexError("Not enough data left to read byte from.")
		self.reset_bit()
		
		value = self.input[self.position]
		if not peek:
			self.position += 1
		return value

	########################
	# Read word            #
	########################
	# ARGUMENTS:           #
	#     peek - Peek flag #
	# RETURNS:             #
	#     Read value       #
	########################

	def read_word(self, peek = False):
		if not self.input:
			raise IndexError("No data to read word from.")

		if (self.position + 2) > len(self.input):
			raise IndexError("Not enough data left to read word from.")
		self.reset_bit()

		value = ((self.input[self.position] << 8) |
			self.input[self.position + 1])
		if not peek:
			self.position += 2
		return value

	########################
	# Read longword        #
	########################
	# ARGUMENTS:           #
	#     peek - Peek flag #
	# RETURNS:             #
	#     Read value       #
	########################

	def read_long(self, peek = False):
		if not self.input:
			raise IndexError("No data to read longword from.")

		if (self.position + 4) > len(self.input):
			raise IndexError("Not enough data left to read longword from.")
		self.reset_bit()

		value = ((self.input[self.position] << 24) |
			(self.input[self.position + 1] << 16) |
			(self.input[self.position + 2] << 8) |
			self.input[self.position + 3])
		if not peek:
			self.position += 4
		return value

	#####################################
	# Read bits                         #
	#####################################
	# ARGUMENTS:                        #
	#     bits - Number of bits to read #
	#     peek - Peek flag              #
	# RETURNS:                          #
	#     Read bits                     #
	#####################################

	def read_bits(self, bits, peek = False):
		if not self.input:
			raise IndexError("No data to read bits from.")

		value = 0
		pos = self.position
		bit = self.bit
		for i in range(0, bits):
			if pos >= len(self.input):
				raise IndexError("Not enough data left to read bits from.")

			value = (value << 1) | ((self.input[pos] >> (7 - bit)) & 1)
			bit += 1
			if (bit >= 8):
				bit = 0
				pos += 1

		if not peek:
			self.position = pos
			self.bit = bit
		return value

	##############################
	# Write byte                 #
	##############################
	# ARGUMENTS:                 #
	#     value - Value to write #
	##############################

	def write_byte(self, value):
		self.output.append(value & 0xFF)

	################################
	# Write list of bytes          #
	################################
	# ARGUMENTS:                   #
	#     values - Values to write #
	################################

	def write_bytes(self, values):
		self.output.extend(values)

	##############################
	# Write word                 #
	##############################
	# ARGUMENTS:                 #
	#     value - Value to write #
	##############################

	def write_word(self, value):
		self.write_byte(value >> 8)
		self.write_byte(value)

	##############################
	# Write longword             #
	##############################
	# ARGUMENTS:                 #
	#     value - Value to write #
	##############################

	def write_long(self, value):
		self.write_word(value >> 16)
		self.write_word(value)

###############################
# Nemesis decompression class #
###############################

class Nemesis(Decompress):

	###########################
	# Decompress Nemesis data #
	###########################

	def decompress(self):
		try:
			self.output = []

			tile_count = self.read_word()
			xor_mode = tile_count >= 0x8000
			row_count = (tile_count & 0x7FFF) * 8
			
			code_lengths = [0] * 256
			code_pixels = [0] * 256
			code_repeats = [0] * 256

			pixel = 0
			while True:
				value = self.read_byte()
				if value >= 0x80:
					if value == 0xFF:
						break
					pixel = value & 0xF
				else:
					length = 8 - (value & 0xF)
					offset = self.read_byte() << length
					for i in range(0, 1 << length):
						code_lengths[offset + i] = value & 0xF
						code_pixels[offset + i] = pixel
						code_repeats[offset + i] = ((value & 0x70) >> 4) + 1

			pixel_count = 8
			pixel_row = 0
			xor_row = 0

			while True:
				index = self.read_bits(8, True)
				if index >= 0b11111100:
					self.read_bits(6)
					pixel = self.read_bits(7)
					repeat = ((pixel & 0x70) >> 4) + 1
					pixel &= 0xF
				else:
					self.read_bits(code_lengths[index])
					pixel = code_pixels[index]
					repeat = code_repeats[index]

				for i in range(0, repeat):
					pixel_row = (pixel_row << 4) | pixel
					pixel_count -= 1
					if pixel_count <= 0:
						if not xor_mode:
							self.write_long(pixel_row)
						else:
							xor_row ^= pixel_row
							self.write_long(xor_row)
						row_count -= 1
						if row_count <= 0:
							return self.output
						pixel_count = 8
						pixel_row = 0
		except Exception as e:
			print(e)
			return None

	####################################
	# Set Nemesis data and decompress  #
	####################################
	# ARGUMENTS:                       #
	#     data     - Data              #
	#     position - Data position     #
	####################################

	def decompress_data(self, data, position = 0):
		self.set_input(data, position)
		return self.decompress()

	########################################
	# Set Nemesis file data and decompress #
	########################################
	# ARGUMENTS:                           #
	#     filename - Filename              #
	########################################

	def decompress_file(self, filename):
		if not self.open_file(filename):
			return None
		return self.decompress()

##############################
# Enigma decompression class #
##############################

class Enigma(Decompress):
	tile_base = 0
	tile_bits = 0
	tile_flags = 0

	###################
	# Get inline tile #
	###################
	# RETURNS:        #
	#     Inline tile #
	###################

	def get_inline(self):
		tile = self.tile_base
		if (self.tile_flags & 0x10) != 0:
			if self.read_bits(1) == 1:
				tile |= 0x8000
		if (self.tile_flags & 8) != 0:
			if self.read_bits(1) == 1:
				tile += 0x4000
		if (self.tile_flags & 4) != 0:
			if self.read_bits(1) == 1:
				tile += 0x2000
		if (self.tile_flags & 2) != 0:
			if self.read_bits(1) == 1:
				tile |= 0x1000
		if (self.tile_flags & 1) != 0:
			if self.read_bits(1) == 1:
				tile |= 0x800
		return tile + self.read_bits(self.tile_bits)

	######################################
	# Decompress Enigma data             #
	######################################
	# ARGUMENTS:                         #
	#     tile_base - Base tile ID/flags #
	######################################

	def decompress(self, tile_base):
		try:
			self.output = []

			self.tile_base = tile_base
			self.tile_bits = self.read_byte()
			self.tile_flags = self.read_byte()
			tile_inc = self.read_word() + tile_base
			tile_static = self.read_word() + tile_base

			while True:
				if self.read_bits(1) == 0:
					mode = self.read_bits(1)
					length = self.read_bits(4) + 1
					for i in range(0, length):
						if mode == 0:
							self.write_word(tile_inc)
							tile_inc += 1
						else:
							self.write_word(tile_static)
				else:
					mode = self.read_bits(2)
					length = self.read_bits(4) + 1
					if mode < 3:
						inline = self.get_inline()
						for i in range(0, length):
							self.write_word(inline)
							if mode == 1:
								inline += 1
							elif mode == 2:
								inline -= 1
					else:
						if length == 0x10:
							return self.output
						for i in range(0, length):
							self.write_word(self.get_inline())
			
		except Exception as e:
			print(e)
			return None

	######################################
	# Set Enigma data and decompress     #
	######################################
	# ARGUMENTS:                         #
	#     data      - Data               #
	#     tile_base - Base tile ID/flags #
	#     position  - Data position      #
	######################################

	def decompress_data(self, data, tile_base = 0, position = 0):
		self.set_input(data, position)
		return self.decompress(tile_base)

	#######################################
	# Set Enigma file data and decompress #
	#######################################
	# ARGUMENTS:                          #
	#     filename - Filename             #
	#     tile_base - Base tile ID/flags  #
	#######################################

	def decompress_file(self, filename, tile_base = 0):
		if not self.open_file(filename):
			return None
		return self.decompress(tile_base)

################################
# Kosinski decompression class #
################################

class Kosinski(Decompress):
	descriptor = 0
	descriptor_bit = 0

	####################
	# Reset descriptor #
	####################

	def reset_descriptor(self):
		self.descriptor = self.read_byte() | (self.read_byte() << 8)
		self.descriptor_bit = 0

	############################
	# Read descriptor bit      #
	############################
	# RETURNS:                 #
	#     Descriptor bit       #
	############################

	def read_descriptor_bit(self):
		value = (self.descriptor >> self.descriptor_bit) & 1
		self.descriptor_bit += 1
		if self.descriptor_bit >= 16:
			self.reset_descriptor()
		return value

	############################
	# Decompress Kosinski data #
	############################

	def decompress(self):
		try:
			self.output = []
			self.reset_descriptor()

			while True:
				if self.read_descriptor_bit() == 0:
					if self.read_descriptor_bit() == 0:
						count = ((self.read_descriptor_bit() << 1) | self.read_descriptor_bit()) + 2
						offset = self.read_byte() - 0x100
					else:
						low = self.read_byte()
						high = self.read_byte()
						offset = (((high & 0xF8) - 0x100) << 5) + low
						count = (high & 7) + 2
						if count == 2:
							count = self.read_byte() + 1
							if count == 1:
								return self.output
							elif count == 2:
								continue
							
					for i in range(0, count):
						self.write_byte(self.output[len(self.output) + offset])
				else:
					value = self.read_byte()
					self.write_byte(value)
			
		except Exception as e:
			print(e)
			return None

	####################################
	# Set Kosinski data and decompress #
	####################################
	# ARGUMENTS:                       #
	#     data     - Data              #
	#     position - Data position     #
	####################################

	def decompress_data(self, data, position = 0):
		self.set_input(data, position)
		return self.decompress()

	#########################################
	# Set Kosinski file data and decompress #
	#########################################
	# ARGUMENTS:                            #
	#     filename - Filename               #
	#########################################

	def decompress_file(self, filename):
		if not self.open_file(filename):
			return None
		return self.decompress()

########################################
# Kosinski Moduled decompression class #
########################################

class KosinskiModuled(Decompress):
	kosinski = None

	####################################
	# Decompress Kosinski Moduled data #
	####################################

	def decompress(self):
		try:
			self.output = []
			self.kosinski = Kosinski()

			size = self.read_word()
			while size > 0:
				self.write_bytes(self.kosinski.decompress_data(self.input, self.position))
				self.position = self.kosinski.position + ((2 - self.kosinski.position) & 0xF)
				size -= 0x1000
			return self.output
			
		except Exception as e:
			print(e)
			return None

	############################################
	# Set Kosinski Moduled data and decompress #
	############################################
	# ARGUMENTS:                               #
	#     data     - Data                      #
	#     position - Data position             #
	############################################

	def decompress_data(self, data, position = 0):
		self.set_input(data, position)
		return self.decompress()

	#################################################
	# Set Kosinski Moduled file data and decompress #
	#################################################
	# ARGUMENTS:                                    #
	#     filename - Filename                       #
	#################################################

	def decompress_file(self, filename):
		if not self.open_file(filename):
			return None
		return self.decompress()
