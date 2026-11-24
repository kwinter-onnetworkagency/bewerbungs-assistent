from public_files import checked_files

if __name__ == "__main__":
    try:
        files = checked_files()
    except ValueError as exc:
        raise SystemExit(str(exc))
    print(f"PUBLIC SOURCE CHECK OK ({len(files)} files)")
