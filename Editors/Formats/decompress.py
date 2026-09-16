#######################
# Decompression class #
#######################

class Decompress:
	def __init__(self, data_input):
		self.data_input = data_input
		self.position = 0
		self.bit = 0
		self.output = []

	######################################
	# Set input data                     #
	######################################
	# ARGUMENTS:                         #
	#     data - Input data              #
	#     position - Input data position #
	######################################

	def set_input(self, data, position = 0):
		self.data_input = data
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
		if not self.data_input:
			raise IndexError("No data to read byte from.")

		if self.position >= len(self.data_input):
			raise IndexError("Not enough data left to read byte from.")
		self.reset_bit()
		
		value = self.data_input[self.position]
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
		if not self.data_input:
			raise IndexError("No data to read word from.")

		if (self.position + 2) > len(self.data_input):
			raise IndexError("Not enough data left to read word from.")
		self.reset_bit()

		value = ((self.data_input[self.position] << 8) |
			self.data_input[self.position + 1])
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
		if not self.data_input:
			raise IndexError("No data to read longword from.")

		if (self.position + 4) > len(self.data_input):
			raise IndexError("Not enough data left to read longword from.")
		self.reset_bit()

		value = ((self.data_input[self.position] << 24) |
			(self.data_input[self.position + 1] << 16) |
			(self.data_input[self.position + 2] << 8) |
			self.data_input[self.position + 3])
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
		if not self.data_input:
			raise IndexError("No data to read bits from.")

		value = 0
		pos = self.position
		bit = self.bit
		for i in range(0, bits):
			if pos >= len(self.data_input):
				raise IndexError("Not enough data left to read bits from.")

			value = (value << 1) | ((self.data_input[pos] >> (7 - bit)) & 1)
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
				# Devon's code (and the original decomp) originally performed a fixed 8-bit peek
				# (A final Huffman code might need only 1 bit, yet the decoder still tries to peek at 8.)
				# Raised an error if any of those eight bits extend beyond the supplied data.
				# Instead, peek at up to 8 bits, and fill out the rest with zeroes

				# Peek at up to eight real bits.
				available = min(8, (len(self.data_input) - self.position) * 8 - self.bit)

				if available <= 0:
					raise IndexError("Not enough data left to decode a Nemesis run.")

				# Zero-fill missing low bits for the table lookup only.
				index = self.read_bits(available, True) << (8 - available)

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

################################
# Kosinski decompression class #
################################

class Kosinski(Decompress):
	def __init__(self, data_input):
		super().__init__(data_input)
		self.descriptor = 0
		self.descriptor_bit = 0

	def reset_descriptor(self):
		self.descriptor = self.read_byte() | (self.read_byte() << 8)
		self.descriptor_bit = 0

	def read_descriptor_bit(self):
		value = (self.descriptor >> self.descriptor_bit) & 1
		self.descriptor_bit += 1
		if self.descriptor_bit >= 16:
			self.reset_descriptor()
		return value

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

	# Called by Moduled Kosinski class
	def decompress_data(self, data, position = 0):
		self.set_input(data, position)
		return self.decompress()

########################################
# Moduled Kosinski decompression class #
########################################

class Kosinski_M(Decompress):
	def __init__(self, data_input):
		super().__init__(data_input)
		self.kosinski = None

	def decompress(self):
		try:
			self.output = []
			self.kosinski = Kosinski(self.data_input)

			size = self.read_word()
			while size > 0:
				self.write_bytes(self.kosinski.decompress_data(self.data_input, self.position))
				self.position = self.kosinski.position + ((2 - self.kosinski.position) & 0xF)
				size -= 0x1000
			return self.output

		except Exception as e:
			print(e)
			return None

#########################
# Decompression callers #
#########################

def nemesis(data):
	decomp = Nemesis(data)
	return decomp.decompress()

def kosinski(data):
	decomp = Kosinski(data)
	return decomp.decompress()

def kosinski_mod(data):
	decomp = Kosinski_M(data)
	return decomp.decompress()
