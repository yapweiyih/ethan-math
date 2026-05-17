"""Test script for server-side auth APIs."""
import server

# Clean start
import os
if server.DB_PATH.exists():
    os.remove(server.DB_PATH)
server.init_db()

print("DB initialized:", server.DB_PATH.exists())

# Test register
r = server.auth_register(server.AuthPayload(username="testuser", password="abc"))
print("Register:", r)
assert r["ok"], "Register failed"
assert r["playerId"], "No playerId"

# Test login
r = server.auth_login(server.AuthPayload(username="testuser", password="abc"))
print("Login:", r)
assert r["ok"], "Login failed"

# Test wrong password
r = server.auth_login(server.AuthPayload(username="testuser", password="wrong"))
print("Wrong pw:", r)
assert r["error"] == "wrong_password"

# Test verify
r = server.auth_verify(server.UsernamePayload(username="testuser"))
print("Verify:", r)
assert r["ok"]

# Test display name update
r = server.auth_update_display_name(
    server.DisplayNamePayload(username="testuser", displayName="Test User")
)
print("Display name:", r)
assert r["ok"]

# Verify display name was updated
r2 = server.auth_verify(server.UsernamePayload(username="testuser"))
assert r2["displayName"] == "Test User"

# Test lookup by player ID
pid = r2["playerId"]
r = server.auth_lookup_player(pid)
print("Lookup:", r)
assert r["ok"]
assert r["username"] == "testuser"

# Test change password
r = server.auth_change_password(
    server.PasswordChangePayload(
        username="testuser", oldPassword="abc", newPassword="xyz"
    )
)
print("Change pw:", r)
assert r["ok"]

# Test login with new password
r = server.auth_login(server.AuthPayload(username="testuser", password="xyz"))
print("Login new pw:", r)
assert r["ok"]

# Test delete
r = server.auth_delete_user("testuser")
print("Delete:", r)
assert r["ok"]

# Test login after delete
r = server.auth_login(server.AuthPayload(username="testuser", password="xyz"))
print("Login after delete:", r)
assert r["error"] == "not_found"

# Test duplicate register
server.auth_register(server.AuthPayload(username="user2", password="abc"))
r = server.auth_register(server.AuthPayload(username="user2", password="abc"))
print("Dup register:", r)
assert r["error"] == "exists"

print()
print("All tests passed!")
