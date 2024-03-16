import psutil, sys, json

if __name__ == "__main__":
    try:
        print([psutil.virtual_memory()[2], psutil.cpu_percent(1)])
        exit(0)
    except Exception as e:
        print(e)
        sys.exit(1)