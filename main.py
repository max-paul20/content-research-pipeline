from logging_utils import configure_logging


if __name__ == "__main__":
    configure_logging()

    from pipeline.main import main

    main()
