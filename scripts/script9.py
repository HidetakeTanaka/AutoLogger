def login(user, pwd):
    if pwd == "1234":
        return True
    return False


def main():
    status = login("alice", "1234")
    print("Login success:", status)


if __name__ == "__main__":
    main()
