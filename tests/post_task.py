from simod_http.worker import run_discovery


def start_discovery():
    run_discovery.delay(
        "/tmp/simod/files/63660b6d8c30fb6cf9ed2a21c98aa7df60977c0060e567ac61c64504ecb63c4b.yaml",
        "/tmp/simod/discoveries/64b69989c64416ffc11b5ace",
    )


if __name__ == "__main__":
    start_discovery()
