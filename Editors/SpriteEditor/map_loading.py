import PyQt6.QtWidgets as QtW

# In the future, additional user-defined formats will be possible
# For that reason, this is stored outside of the loading functions
MAP_FORMATS = {
	1: {
		'header_size': 1,
		'piece_size': 5,
		'attr_bytes': 2,
		'x_bytes': 1
	},
	2: {
		'header_size': 2,
		'piece_size': 8,
		'attr_bytes': 4,
		'x_bytes': 2
	},
	3: {
		'header_size': 2,
		'piece_size': 6,
		'attr_bytes': 2,
		'x_bytes': 2
	}
}

# Top-level spritemap loader
def load_mappings(editor, path, map_version=1):
    if path.suffix.lower() == '.asm':
        load_mappings_asm(editor, path, map_version)
    else:
        load_mappings_bin(editor, path, map_version)

def load_mappings_asm(editor, path, map_version=1):
    contents = []

    # Get all content, removing comments & lead/trail whitespace
    with open(path, 'r') as f:
        for line in f:
            line = line.split(';', 1)[0].strip()

            if line:
                contents.append(line)

    # MapMacros check (Returned ASM command == mappingstableentry)
    if any(
        split_asm_line(line)[1].startswith('mappingstableentry')
        for line in contents
    ):
        # Jump to new loading function
        load_mappings_macro(editor, contents)
        return

    # Traditional ASM mapping files (Change this to use identical structure to macro version)
    map_label = None    # Get top-level map label
    frame_labels = []   # Get ordered frame labels from the pointer table

    # Get map frame attributes based on mapping version
    map_format = MAP_FORMATS[map_version]
    header_size = map_format['header_size']  # Number of bytes for the frame's piece count
    piece_size = map_format['piece_size']  # Number of bytes per piece for each frame

    # Get top-level map label (if it is in the file)
    if contents:
        first_label, _, _ = split_asm_line(contents[0])

        if first_label:
            map_label = first_label

    # Track the end of the pointer table so we can remove the header afterwards
    # It's far easier to just cut the header than to try indexing stuff early
    pointer_table_end = 0

    # Find frame pointers to get their labels
    for _i, line in enumerate(contents):
        defined_label, command, ptr_str = split_asm_line(line)

        # Once an already defined frame label is found, the pointer table is over
        if frame_labels and defined_label in frame_labels:
            break

        if command != 'dc.w':
            continue

        pointer_table_end = _i + 1  # Track end of pointer table

        # Split by comma in case multiple pointers are on a single line
        for ptr in ptr_str.split(','):
            ptr = ptr.strip()

            # For standard pointers formatted as: frame-base
            if '-' in ptr:
                frame_part, base_part = ptr.split('-', 1)

                # Append a frame label from the pointer
                label = frame_part.strip()
                if label:
                    frame_labels.append(label)

                # Fallback attempt to retrieve a top-level map label
                if not map_label:
                    map_label = base_part.strip()

            # If, for some reason, frame label pointers are not formatted as: frame-base
            else:
                label = ptr.strip()
                if label:
                    frame_labels.append(label)

    # Remove the header
    contents = contents[pointer_table_end:]

    # Now, index frame definitions
    frame_label_set = set(frame_labels)
    frame_starts = {}

    # Frame indexing
    for _i, line in enumerate(contents):
        defined_label, _, _ = split_asm_line(line)

        if defined_label in frame_label_set:
            # .setdefault indexes the defined label only if it hasn't be indexed already.
            # This preserves the definition if a malformed .asm file defines it twice.
            frame_starts.setdefault(defined_label, _i)

    # Used to recognize when collection reaches the next frame
    frame_start_indices = set(frame_starts.values())

    # Locate each frame label and extract its data pieces
    for label in frame_labels:
        # Retrieve the previously indexed frame position
        start_idx = frame_starts.get(label)

        # If the referenced label wasn't found, continue on to the next one
        if start_idx is None:
            QtW.QMessageBox.warning(
                editor, "Mapping Load Error", f"Frame '{label}' is referenced but has no definition."
            )
            continue

        # If the label was found, begin extracting its frame data
        bytes_collected = []
        piece_count = None
        expected_bytes = None
        frame_has_error = False  # Flag noting to skip frame due to erroneous data

        # Sprite piece data collection
        for _i in range(start_idx, len(contents)):
            line = contents[_i]

            # Stop when another indexed frame begins
            if _i != start_idx and _i in frame_start_indices:
                break

            # Get data line here in case frame_label and dc._ share the same line
            # (e.g.: M_Hog_Stand:   dc.b 2)
            _, command, piece = split_asm_line(line)

            # Ignore lines that aren't data declarations
            if not command.startswith('dc.'):
                continue

            # Process all dc._ types to support S2/S3 word alignment
            data_type = command[3:]  # b or w (l is also possible)

            # Handle invalid declaration types
            if data_type not in ('b', 'w', 'l'):
                QtW.QMessageBox.warning(
                    editor, "Mapping Load Error", f"Frame '{label}' uses unsupported declaration " +
                    f"'{command}' in line: {line}"
                )
                frame_has_error = True
                continue

            # Look through each item in mapping piece data
            for _p in piece.split(','):
                _p = _p.strip()

                # if no data is present, continue onward
                if not _p:
                    continue

                try:
                    # Collect all bytes for this piece (determine hex or decimal)
                    val = parse_asm_number(_p)

                    if data_type == 'b':
                        bytes_collected.append(val & 0xFF)
                    elif data_type == 'w':
                        bytes_collected.extend([(val >> 8) & 0xFF, val & 0xFF])
                    elif data_type == 'l':
                        bytes_collected.extend([(val >> 24) & 0xFF, (val >> 16) & 0xFF, (val >> 8) & 0xFF, val & 0xFF])

                # Skip unrecognized text
                except ValueError:
                    QtW.QMessageBox.warning(
                        editor, "Mapping Load Error", f"Frame '{label}' contains an invalid value " +
                        f"{_p!r} in line: {line}"
                    )
                    frame_has_error = True
                    continue

            # Set piece count and expected bytes from the very first byte(s) collected
            if piece_count is None and len(bytes_collected) >= header_size:
                piece_count = int.from_bytes(bytes(bytes_collected[:header_size]), byteorder='big')
                expected_bytes = header_size + piece_count * piece_size

            # Stop when we've collected the expected amount of bytes
            if expected_bytes is not None and len(bytes_collected) >= expected_bytes:
                break

        # Piece data collection finished. Now error-check and build frame
        # Error if there isn't frame data
        if piece_count is None:
            QtW.QMessageBox.warning(
                editor, "Mapping Load Error", f"Frame '{label}' has no readable piece count."
            )
            continue

        # Error if invalid piece data has been found
        if frame_has_error:
            QtW.QMessageBox.warning(
                editor, "Mapping Load Error", f"Frame '{label}' was not loaded because it contains " +
                "invalid piece data."
            )
            continue

        # Incomplete frame data
        if len(bytes_collected) < expected_bytes:
            QtW.QMessageBox.warning(
                editor, "Mapping Load Error", f"Frame '{label}' declares {piece_count} pieces, " +
                f"requiring {expected_bytes} bytes, but only {len(bytes_collected)} were found."
            )
            continue

        # Excess frame data
        if len(bytes_collected) > expected_bytes:
            QtW.QMessageBox.warning(
                editor, "Mapping Load Error", f"Frame '{label}' contains " +
                f"{len(bytes_collected) - expected_bytes} undeclared trailing byte(s)."
            )

        # Construct mapping frame list
        frame_data = extract_frame_pieces(bytes_collected, header_size, piece_count, map_format)

        # Append to map frames data
        editor.map_frames.append(frame_data)

def load_mappings_macro(editor, contents):
    map_label = None    # Top-level map label
    frame_labels = []   # Ordered frame labels from the pointer table
    frame_starts = {}   # Dictionary: {frame_label: starting line index}

    # Run through contents to find labels
    for _i, line in enumerate(contents):
        defined_label, command, data = split_asm_line(line)

        if not command:
            continue

        # Find top-level map label
        if command == 'mappingstable' and defined_label:
            map_label = defined_label

        # Find frame pointers to get their labels
        elif command.startswith('mappingstableentry') and data:
            for entry in data.split(','):
                entry = entry.strip()
                if entry:
                    frame_labels.append(entry)

        # Frame indexing
        elif command == 'spriteheader' and defined_label:
            frame_starts[defined_label] = _i

    # With all labels found, create reverse lookup
    # {line number: frame label}
    frame_at_start = {
        start_idx: frame_label
        for frame_label, start_idx in frame_starts.items()
    }

    # if map_label == None, it will be user-specified in the editor

    # Locate each frame label and extract its data pieces
    for label in frame_labels:
        # If this frame has no spriteHeader definition, skip it
        if label not in frame_starts:
            QtW.QMessageBox.warning(
                editor, "Mapping Load Error", f"Frame '{label}' is referenced "+
                "but has no spriteHeader definition."
            )
            continue

        # Construct mapping frame list
        frame_data = []
        start_idx = frame_starts[label]

        # Start at the line AFTER the label and command
        for _i in range(start_idx + 1, len(contents)):
            line = contents[_i]

            # if another spriteHeader is found, this frame's missing an _End
            if frame_at_start.get(_i) is not None:
                QtW.QMessageBox.warning(
                    editor, "Mapping Load Error", f"Frame '{label}' is missing its _End label:" +
                    f"{label}_End. Stopped at the next spriteHeader."
                )
                break

            # Frame boundary check
            if line.split(None, 1)[0].rstrip(':') == label + '_End':
                break

            _, command, data = split_asm_line(line)

            # If the first part wasn't "spritePiece", move on to the next frame
            if command != 'spritepiece':
                continue

            if not data:
                QtW.QMessageBox.warning(
                    editor, "Mapping Load Error", f"Frame '{label}' has a spritePiece " +
                    "with no values."
                )
                continue

            # Get data directly from the values AFTER spritePiece
            try:
                values = [parse_asm_number(value) for value in data.split(',')]

            # If there is an erroneous value, move on to the next frame
            except ValueError as error:
                QtW.QMessageBox.warning(
                    editor, "Mapping Load Error", f"Frame '{label}' contains an invalid " +
                    f"spritePiece value in line: {line} ({error})."
                )
                continue

            # If there's an invalid number of values, move on to the next frame
            if len(values) != 9:
                QtW.QMessageBox.warning(
                    editor, "Mapping Load Error", f"Frame '{label}' has a spritePiece " +
                    f"{len(values)} values; Expected: 9. Line: {line}."
                )
                continue

            # Assign everything from values list, then perform validation checks
            x, y, width, height, tile, x_flip, y_flip, palette, priority = values

            # If map piece sizes are invalid, move on to the next frame
            if not 1 <= width <= 4 or not 1 <= height <= 4:
                QtW.QMessageBox.warning(
                    editor, "Mapping Load Error", f"Frame '{label}' has invalid dimensions " +
                    f"{width}x{height}; width and height must be 1–4."
                )
                continue

            # If flip flags have been given erroneous values, move on to the next frame
            if x_flip not in (0, 1) or y_flip not in (0, 1):
                QtW.QMessageBox.warning(
                    editor, "Mapping Load Error", f"Frame '{label}' has invalid flip flags. " +
                    f"Flip flags must be 0 or 1."
                )
                continue

            # If map piece sizes are invalid, move on to the next frame
            if not 0 <= palette <= 3:
                QtW.QMessageBox.warning(
                    editor, "Mapping Load Error", f"Frame '{label}'  has invalid palette {palette}. " +
                    f"Palette line index must be 0–3."
                )
                continue

            # If flip flags have been given erroneous values, move on to the next frame
            if priority not in (0, 1):
                QtW.QMessageBox.warning(
                    editor, "Mapping Load Error", f"Frame '{label}' has invalid priority {priority}. " +
                    f"Priority flag must be 0 or 1."
                )
                continue

            # Append raw piece data
            frame_data.append({
                'x': x,
                'y': y,
                'width': width,
                'height': height,
                'tile': tile,
                'x_flip': x_flip,
                'y_flip': y_flip,
                'palette': palette,
                'priority': priority
            })

        # The final frame may reach EOF without encountering another spriteHeader
        else:
            QtW.QMessageBox.warning(
                editor, "Mapping Load Error", f"Frame '{label}' is missing its '{label}_End' label; "
                "reached the end of the file."
            )

        # Append to map frames data
        editor.map_frames.append(frame_data)

def load_mappings_bin(editor, path, map_version=1):
    # Store all bytes from the binary file in a list
    with open(path, "rb") as f:
        raw = f.read()

    # If this mapping file has no frame data, stop now
    if len(raw) < 2:
        QtW.QMessageBox.warning(
            editor, "Mapping Load Error", "File is too short to contain a mapping pointer table."
        )
        return

    # Mappings begin with an array of word-length offsets for each frame.
    # Because the first mapping is expected immediately after this array,
    # the total number of frames is assumed to be the first offset div 2.
    first_offset = (raw[0] << 8) | raw[1]
    num_frames = first_offset // 2

    # Get map frame attributes based on mapping version
    map_format = MAP_FORMATS[map_version]
    header_size = map_format['header_size']  # Number of bytes for the frame's piece count
    piece_size = map_format['piece_size']  # Number of bytes per piece for each frame

    for _i in range(num_frames):
        pointer_pos = _i * 2

        # Make sure both bytes of this pointer exist
        if pointer_pos + 1 >= len(raw):
            QtW.QMessageBox.warning(
                editor, "Mapping Load Error", f"Pointer table is truncated at frame index {_i}."
            )
            break

        # Get word value directing to the next mapping frame
        offset = (raw[pointer_pos] << 8) | raw[pointer_pos + 1]

        # Get starting pointer of the next mapping frame
        start_ptr = offset + header_size

        # Skip offsets that do not contain a complete frame header
        if start_ptr > len(raw):
            QtW.QMessageBox.warning(
                editor, "Mapping Load Error", f"Frame {_i} points to offset ${offset:X}, " +
                "which does not contain a complete frame header."
            )
            continue

        # Read the piece count from the frame header
        piece_count = int.from_bytes(raw[offset:start_ptr], byteorder='big')

        # Get pointer for expected end of frame
        frame_end = start_ptr + piece_count * piece_size

        # Reject incomplete frames
        if frame_end > len(raw):
            available = len(raw) - start_ptr
            required = piece_count * piece_size

            QtW.QMessageBox.warning(
                editor, "Mapping Load Error", f"Frame {_i} declares {piece_count} pieces requiring " +
                f"{required} data bytes, but only {available} remain."
            )
            continue

        # Construct mapping frame list
        frame_data = extract_frame_pieces(raw, start_ptr, piece_count, map_format)

        # Append to map frames data
        editor.map_frames.append(frame_data)

def split_asm_line(line):
    label = None
    clean_line = line.strip()   # is this needed (assuming lines are already stripped?)

    # Separate label from the rest of the line
    if ':' in clean_line:
        label, clean_line = clean_line.split(':', 1)
        label = label.strip()
        clean_line = clean_line.strip()

    # Separate command from data (split on whitespace)
    parts = clean_line.split(None, 1)

    # Return if the label is alone on this line
    if not parts:
        return label, '', ''

    command = parts[0].lower()
    data = parts[1].strip() if len(parts) == 2 else ''

    # Return all contents in this line, split apart
    return label, command, data

def parse_asm_number(value):
    value = value.strip()
    sign = 1

    # Check for sign operator, apply sign, and remove operator
    if value.startswith(('+', '-')):
        if value[0] == '-':
            sign = -1
        value = value[1:].strip()

    # Convert hex value
    if value.startswith('$'):
        value = int(value[1:], 16)
    # Convert binary value
    elif value.startswith('%'):
        value = int(value[1:], 2)
    else:
        value = int(value)

    # Return signed int
    return sign * value

# Used by standard ASM and BIN loading
def extract_frame_pieces(data_array, start_ptr, piece_count, map_format):
    # Construct mapping frame list
    frame_data = []

    # Initialize frame piece pointer
    ptr = start_ptr

    # Get piece attributes from map format
    piece_size = map_format['piece_size']
    attr_bytes = map_format['attr_bytes']
    x_bytes = map_format['x_bytes']

    # Iterate through frame pieces
    for _ in range(piece_count):
        # Safety check for binary EOF
        if ptr + piece_size > len(data_array):
            break

        # Y Offset (signed)
        y = data_array[ptr]
        if y > 127:
            y -= 256
        ptr += 1

        # Piece size
        size = data_array[ptr]
        width = ((size >> 2) & 3) + 1
        height = (size & 3) + 1
        ptr += 1

        # VDP attributes
        attributes = (data_array[ptr] << 8) | data_array[ptr + 1]

        # Break apart this word value
        # Sonic 2's 2P bytes get skipped
        tile = attributes & 0x7FF
        x_flip = (attributes >> 11) & 1
        y_flip = (attributes >> 12) & 1
        palette = (attributes >> 13) & 3
        priority = (attributes >> 15) & 1
        ptr += attr_bytes

        # X Offset (signed)
        x = int.from_bytes(
            bytes(data_array[ptr:ptr + x_bytes]),
            byteorder='big',
            signed=True
        )
        ptr += x_bytes

        # Append raw piece data
        frame_data.append({
            'x': x,
            'y': y,
            'width': width,
            'height': height,
            'tile': tile,
            'x_flip': x_flip,
            'y_flip': y_flip,
            'palette': palette,
            'priority': priority
        })

    # Return frame list
    return frame_data
