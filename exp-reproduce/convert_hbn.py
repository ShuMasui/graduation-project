"""
exp-reproduce/convert_hbn.py
HBN EEG (MAT/CSV) dataset downloader and converter to MNE Raw FIF format.

Downloads NDARAA075AMK and NDARAA117NEJ (RestingState, Video1) from AWS S3,
loads EEG data, sets GSN-HydroCel-128 montage, and exports to .fif format.
"""
import os
import sys
import urllib.request
import numpy as np
import scipy.io
import mne

HBN_S3_BASE = "https://fcp-indi.s3.amazonaws.com/data/Projects/HBN/EEG"

SUBJECTS = ["NDARAA075AMK", "NDARAA117NEJ"]
TASKS = ["RestingState", "Video1"]

def download_file(url: str, dest_path: str):
    """Download a file from HTTP/S3 with progress reporting."""
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    if os.path.exists(dest_path) and os.path.getsize(dest_path) > 0:
        print(f"Already downloaded: {dest_path} ({os.path.getsize(dest_path)} bytes)")
        return

    print(f"Downloading {url} -> {dest_path}...")
    def _reporthook(block_num, block_size, total_size):
        if total_size > 0:
            percent = block_num * block_size / total_size * 100
            if block_num % 500 == 0:
                print(f"  {percent:.1f}% ({block_num * block_size}/{total_size} bytes)")
        else:
            if block_num % 500 == 0:
                print(f"  Downloaded {block_num * block_size} bytes...")

    try:
        urllib.request.urlretrieve(url, dest_path, reporthook=_reporthook)
        print(f"Download complete: {dest_path} ({os.path.getsize(dest_path)} bytes)")
    except Exception as e:
        print(f"Error downloading {url}: {e}")
        # If download failed, clean up partial file
        if os.path.exists(dest_path):
            os.remove(dest_path)
        raise e


def load_hbn_mat(mat_path: str):
    """Load EEG data from HBN MAT file.
    
    Returns:
        data: np.ndarray of shape (n_channels, n_samples)
        sfreq: float sampling frequency (Hz)
    """
    try:
        mat = scipy.io.loadmat(mat_path, struct_as_record=False, squeeze_me=True)
    except NotImplementedError:
        # v7.3 MAT files (HDF5)
        import h5py
        with h5py.File(mat_path, "r") as f:
            print("Loaded via h5py keys:", list(f.keys()))
            if "EEG" in f:
                eeg_group = f["EEG"]
                data = np.array(eeg_group["data"])
                # In HDF5 MATLAB matrices are transposed (samples, channels) or similar
                if data.ndim == 2:
                    if data.shape[0] > data.shape[1]:
                        data = data.T
                sfreq = float(np.array(eeg_group["srate"]).ravel()[0])
                return data, sfreq
            elif "data" in f:
                data = np.array(f["data"])
                if data.ndim == 2 and data.shape[0] > data.shape[1]:
                    data = data.T
                sfreq = 500.0
                return data, sfreq
            raise ValueError(f"Unknown h5py structure in {mat_path}")

    # Standard scipy loadmat
    if "EEG" in mat:
        eeg_obj = mat["EEG"]
        if hasattr(eeg_obj, "data"):
            data = eeg_obj.data
        else:
            data = mat["EEG"]["data"]

        if hasattr(eeg_obj, "srate"):
            sfreq = float(eeg_obj.srate)
        else:
            sfreq = 500.0
    elif "data" in mat:
        data = mat["data"]
        sfreq = float(mat.get("srate", 500.0))
    elif "EEG_data" in mat:
        data = mat["EEG_data"]
        sfreq = 500.0
    else:
        # Find 2D float array in keys
        candidates = [k for k in mat.keys() if not k.startswith("__") and isinstance(mat[k], np.ndarray) and mat[k].ndim == 2]
        if candidates:
            data = mat[candidates[0]]
            sfreq = 500.0
        else:
            raise ValueError(f"Cannot identify EEG data in {mat_path}. Keys: {list(mat.keys())}")

    # Ensure shape is (n_channels, n_samples)
    if data.ndim == 3:
        # e.g., (channels, samples, epochs) or (epochs, channels, samples)
        print(f"Data is 3D with shape {data.shape}, concatenating epochs...")
        if data.shape[0] in [128, 129]:
            data = data.reshape(data.shape[0], -1)
        elif data.shape[1] in [128, 129]:
            data = np.transpose(data, (1, 0, 2)).reshape(data.shape[1], -1)
        else:
            data = data.reshape(data.shape[0], -1)

    if data.shape[0] > data.shape[1] and data.shape[1] in [128, 129]:
        data = data.T

    return data, sfreq


def convert_mat_to_mne_raw(mat_path: str, montage_name: str = "GSN-HydroCel-128") -> mne.io.RawArray:
    """Convert HBN EEG data into mne.io.RawArray with GSN-HydroCel-128 montage."""
    data, sfreq = load_hbn_mat(mat_path)
    print(f"Loaded data shape: {data.shape}, sfreq: {sfreq}")

    montage = mne.channels.make_standard_montage(montage_name)
    standard_ch_names = montage.ch_names  # E1, E2, ..., E128

    n_channels, n_samples = data.shape

    # Handle 128 or 129 channels
    if n_channels == 129:
        print("Trimming 129th channel (vertex reference Cz/VREF) to match 128 channels...")
        data = data[:128, :]
        ch_names = standard_ch_names[:128]
    elif n_channels == 128:
        ch_names = standard_ch_names[:128]
    elif n_channels < 128:
        print(f"Warning: Only {n_channels} channels available.")
        ch_names = standard_ch_names[:n_channels]
    else:
        print(f"Trimming {n_channels} channels to 128.")
        data = data[:128, :]
        ch_names = standard_ch_names[:128]

    # Convert units: HBN raw EEG is in microvolts (uV).
    # MNE expects Volts (V).
    data_std = np.nanstd(data)
    data_max = np.nanmax(np.abs(data))
    print(f"Data scale check: std={data_std:.2f}, max={data_max:.2f}")
    if data_std > 1e-3:  # If std is > 1 mV, it's definitely in uV
        print("Converting data from uV to V (multiplying by 1e-6)...")
        data = data * 1e-6
    else:
        print("Data already appears to be in Volts.")

    # Remove NaNs if any
    if np.isnan(data).any():
        print("Replacing NaNs with 0...")
        data = np.nan_to_num(data, nan=0.0)

    # Create MNE info and RawArray
    info = mne.create_info(ch_names=ch_names, sfreq=sfreq, ch_types="eeg")
    raw = mne.io.RawArray(data, info, verbose=False)
    raw.set_montage(montage, on_missing="ignore", match_case=False)
    return raw


def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    raw_dir = os.path.join(base_dir, "data", "raw_hbn")
    output_dir = os.path.join(base_dir, "data")
    os.makedirs(raw_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)

    for sub in SUBJECTS:
        sub_raw_dir = os.path.join(raw_dir, sub)
        os.makedirs(sub_raw_dir, exist_ok=True)

        for task in TASKS:
            mat_filename = f"{task}.mat"
            mat_path = os.path.join(sub_raw_dir, mat_filename)
            s3_url = f"{HBN_S3_BASE}/{sub}/EEG/raw/mat_format/{mat_filename}"

            print("=" * 60)
            print(f"Processing Subject: {sub}, Task: {task}")
            print("=" * 60)

            # Download if not present
            download_file(s3_url, mat_path)

            # Convert to MNE Raw
            raw = convert_mat_to_mne_raw(mat_path, montage_name="GSN-HydroCel-128")

            # Save to .fif
            fif_path = os.path.join(output_dir, f"{sub}_{task}_raw.fif")
            print(f"Saving to FIF: {fif_path}...")
            raw.save(fif_path, overwrite=True, verbose=False)
            print(f"Successfully saved {fif_path} (duration: {raw.times[-1]:.1f} s, channels: {len(raw.ch_names)})")

    print("\nAll HBN datasets downloaded and converted successfully!")


if __name__ == "__main__":
    main()
