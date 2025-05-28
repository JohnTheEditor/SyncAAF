import pandas as pd
import re
import streamlit as st
import io
import tempfile
import os

# Final working parser that trims header to match actual data
def parse_working_ale(file_content):
    lines = file_content.decode('utf-8').splitlines()
    
    data_start_idx = next(i for i, line in enumerate(lines) if line.strip() == "Data")
    header = lines[data_start_idx - 2].strip().split('\t')[:5]  # trim to 5 columns
    data_lines = lines[data_start_idx + 1:]

    data = []
    for line in data_lines:
        if line.strip():
            row = line.strip().split('\t')[:5]
            if len(row) == len(header):
                data.append(row)

    df = pd.DataFrame(data, columns=header)

    # Clean and extract A1, A2, etc.
    df["Tracks"] = df["Tracks"].str.replace("V", "", regex=False)
    df["Tracks"] = df["Tracks"].apply(lambda x: " ".join(re.findall(r'A\d+', x)))

    return df[["Tape", "Tracks"]].set_index("Tape")

def transform_edl_with_audio_tracks(edl_content, tape_to_tracks):
    edl_lines = edl_content.decode('utf-8').splitlines()
    
    header_lines = []
    event_blocks = []
    curr_block = []

    # First pass: collect header lines
    for line in edl_lines:
        if not re.match(r'^\d{6}\s', line):  # If it's not an event line
            header_lines.append(line + '\n')
        else:
            break  # Stop when we hit the first event line

    # Second pass: collect event blocks
    for line in edl_lines:
        if re.match(r'^\d{6}\s', line):  # Start of new event
            if curr_block:
                event_blocks.append(curr_block)
                curr_block = []
        curr_block.append(line)
    if curr_block:
        event_blocks.append(curr_block)

    # Process each event block
    new_events = []
    event_counter = 1

    for block in event_blocks:
        event_line = block[0]
        match = re.match(r'^(\d{6})\s+(\S+)\s+(\S+)\s+C\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)', event_line)
        if not match:
            continue

        _, tape, track_type, src_in, src_out, rec_in, rec_out = match.groups()

        # Only process video events
        if track_type != 'V':
            continue

        # Get track list from ALE, fallback to A1
        audio_tracks_str = tape_to_tracks.get(tape, "A1")
        audio_tracks = audio_tracks_str.split()

        for audio_track in audio_tracks:
            new_event_number = f"{event_counter:06}"
            if audio_track == 'A1':
                new_event_line = f"{new_event_number}  {tape:<129} {'A '}     C        {src_in} {src_out} {rec_in} {rec_out}\n"
            else:
                new_event_line = f"{new_event_number}  {tape:<129} {audio_track:<7}C        {src_in} {src_out} {rec_in} {rec_out}\n"
            modified_block = [new_event_line] + block[1:]
            new_events.extend(modified_block)
            event_counter += 1

    # Create the final EDL content
    final_content = "".join(header_lines)
    for event in new_events:
        final_content += event
        if not event.endswith('\n'):
            final_content += '\n'

    return final_content

# Streamlit UI
st.set_page_config(
    page_title="Sync AAF Tool",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Centered, slightly-wide UI block
left_pad, center_col, right_pad = st.columns([1, 2.5, 1])

with center_col:
    st.title("Easy Sync AAF Tool - In development")
    st.markdown("""
    Use an ALE & a V1 EDL to make a Sync AAF with *all* your audio tracks.

    Your files will never be stored/uploaded/used to train advanced AI Assistant Editors.
   
    ---
    """)
    
    # File uploaders
    uploaded_ale = st.file_uploader("Upload your ALE file", type=["ale"])
    uploaded_edl = st.file_uploader("Upload your EDL file", type=["edl"])

if uploaded_ale and uploaded_edl:
    try:
        # Process ALE file
        ale_df = parse_working_ale(uploaded_ale.getvalue())
        tape_to_tracks = ale_df["Tracks"].to_dict()
        
        # Process EDL file
        base_name = os.path.splitext(uploaded_edl.name)[0]
        new_filename = base_name + "_AllAudioTracks.edl"
        transformed_edl = transform_edl_with_audio_tracks(uploaded_edl.getvalue(), tape_to_tracks)
        
        # Display preview
        st.subheader("EDL Preview")
        st.text_area("Preview", transformed_edl, height=300)
        
        # Download button
        st.download_button(
            label="Download your EDL",
            data=transformed_edl,
            file_name= new_filename,
            mime="text/plain"
        )
        
    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
        st.error("Please make sure your files are in the correct format.")

with center_col:
    st.markdown("""
    ---
    
    Check out this video for a demo of how to use this: (I'll put a video here eventually)
    
    Instructions:
    
    1) Create a V1 EDL: 
        - Flatten your sequence, moving every visible clip down to V1
        - Export this as an EDL, make sure your Tape names are in the event line like so:

                        000008  **A540C008_241009QL**

    2) Create your ALE
        - Drag your V1 sequence into a new bin.
        - Right Click > Set Bin Display... > And select only **"Master Clips"** and **"Show reference clips"**
        - Set your bin view to **only** have the following columns:
        
                        Name    Tracks    Tape    Start    End    Source File
        - Export this ALE to your desktop


    3) Upload & Download
        - Drag and drop into the boxes above, download your shiny new EDL
        


    4) Reimport
        - Use the source browser to reimport this sequence back into Media Composer
        - When Prompted, select **"Don't Map"** under the "Select Audio Mapping" drop down, and continue the import
        - You may get some error messages is respeeds were present, but you can ignore those
        - You should now have a massive timeline of offline audio media, nice!


        
    5) Relink
        - Right click your sequence -> Relink -> Managed Media
        - This step will probably vary and take some tinkering, but generally I use these settings:
            - Select the drive where your media lives
            - Utilize "Tape Name or Source File Name"
            - Tick "Ignore Extension"
            - Untick "Match case when..."
            - Select only "Audio" under "Tracks to relink"
            - Untick "Create New Sequence" if you like
        - Click ok and hope for the best
        - If you've got recaps pulling from other eps, you may need to go episode by episode to get those guys back online



    6) Check
        - Cut back in your original V1 EDL to a video track in your newly relinked sequence and make sure things look good



    7) Export
        - Send that baby out!
    
    ---
    
    If anything is weird, feel free to say so!
    
    **JohnJGrenham@gmail.com**
    """)
