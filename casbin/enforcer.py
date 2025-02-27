from casbin.management_enforcer import ManagementEnforcer
from casbin.util import join_slice, set_subtract


class Enforcer(ManagementEnforcer):
    """
    Enforcer = ManagementEnforcer + RBAC_API + RBAC_WITH_DOMAIN_API
    """

    """creates an enforcer via file or DB.

        File:
            e = casbin.Enforcer("path/to/basic_model.conf", "path/to/basic_policy.csv")
        MySQL DB:
            a = mysqladapter.DBAdapter("mysql", "mysql_username:mysql_password@tcp(127.0.0.1:3306)/")
            e = casbin.Enforcer("path/to/basic_model.conf", a)
    """

    async def get_roles_for_user(self, name):
        """gets the roles that a user has."""
        return self.model.model["g"]["g"].rm.get_roles(name)

    async def get_users_for_role(self, name):
        """gets the users that has a role."""
        return self.model.model["g"]["g"].rm.get_users(name)

    async def has_role_for_user(self, name, role):
        """determines whether a user has a role."""
        roles = await self.get_roles_for_user(name)
        return any(r == role for r in roles)

    async def add_role_for_user(self, user, role):
        """
        adds a role for a user.
        Returns false if the user already has the role (aka not affected).
        """
        return await self.add_grouping_policy(user, role)

    async def delete_role_for_user(self, user, role):
        """
        deletes a role for a user.
        Returns false if the user does not have the role (aka not affected).
        """
        return await self.remove_grouping_policy(user, role)

    async def delete_roles_for_user(self, user):
        """
        deletes all roles for a user.
        Returns false if the user does not have any roles (aka not affected).
        """
        return await self.remove_filtered_grouping_policy(0, user)

    async def delete_user(self, user):
        """
        deletes a user.
        Returns false if the user does not exist (aka not affected).
        """
        res1 = await self.remove_filtered_grouping_policy(0, user)

        res2 = await self.remove_filtered_policy(0, user)
        return res1 or res2

    async def delete_role(self, role):
        """
        deletes a role.
        Returns false if the role does not exist (aka not affected).
        """
        res1 = await self.remove_filtered_grouping_policy(1, role)

        res2 = self.remove_filtered_policy(0, role)
        return res1 or res2

    async def delete_permission(self, *permission):
        """
        deletes a permission.
        Returns false if the permission does not exist (aka not affected).
        """
        return await self.remove_filtered_policy(1, *permission)

    async def add_permission_for_user(self, user, *permission):
        """
        adds a permission for a user or role.
        Returns false if the user or role already has the permission (aka not affected).
        """
        return await self.add_policy(join_slice(user, *permission))

    async def delete_permission_for_user(self, user, *permission):
        """
        deletes a permission for a user or role.
        Returns false if the user or role does not have the permission (aka not affected).
        """
        return await self.remove_policy(join_slice(user, *permission))

    async def delete_permissions_for_user(self, user):
        """
        deletes permissions for a user or role.
        Returns false if the user or role does not have any permissions (aka not affected).
        """
        return await self.remove_filtered_policy(0, user)

    async def get_permissions_for_user(self, user):
        """
        gets permissions for a user or role.
        """
        return await self.get_filtered_policy(0, user)

    async def has_permission_for_user(self, user, *permission):
        """
        determines whether a user has a permission.
        """
        return await self.has_policy(join_slice(user, *permission))

    async def get_implicit_roles_for_user(self, name, domain=None):
        """
        gets implicit roles that a user has.
        Compared to get_roles_for_user(), this function retrieves indirect roles besides direct roles.
        For example:
        g, alice, role:admin
        g, role:admin, role:user

        get_roles_for_user("alice") can only get: ["role:admin"].
        But get_implicit_roles_for_user("alice") will get: ["role:admin", "role:user"].
        """
        res = []
        queue = [name]

        while queue:
            name = queue.pop(0)

            for rm in self.rm_map.values():
                roles = rm.get_roles(name, domain)
                for r in roles:
                    if r not in res:
                        res.append(r)
                        queue.append(r)

        return res

    async def get_implicit_permissions_for_user(self, user, domain=None):
        """
        gets implicit permissions for a user or role.
        Compared to get_permissions_for_user(), this function retrieves permissions for inherited roles.
        For example:
        p, admin, data1, read
        p, alice, data2, read
        g, alice, admin

        get_permissions_for_user("alice") can only get: [["alice", "data2", "read"]].
        But get_implicit_permissions_for_user("alice") will get: [["admin", "data1", "read"], ["alice", "data2", "read"]].
        """
        roles = await self.get_implicit_roles_for_user(user, domain)

        roles.insert(0, user)

        res = []
        for role in roles:
            if domain:
                permissions = await self.get_permissions_for_user_in_domain(
                    role, domain
                )
            else:
                permissions = await self.get_permissions_for_user(role)

            res.extend(permissions)

        return res

    async def get_implicit_users_for_permission(self, *permission):
        """
        gets implicit users for a permission.
        For example:
        p, admin, data1, read
        p, bob, data1, read
        g, alice, admin

        get_implicit_users_for_permission("data1", "read") will get: ["alice", "bob"].
        Note: only users will be returned, roles (2nd arg in "g") will be excluded.
        """
        subjects = self.get_all_subjects()
        roles = self.get_all_roles()

        users = set_subtract(subjects, roles)

        res = list()
        for user in users:
            req = join_slice(user, *permission)
            allowed = self.enforce(*req)

            if allowed:
                res.append(user)

        return res

    async def get_roles_for_user_in_domain(self, name, domain):
        """gets the roles that a user has inside a domain."""
        return self.model.model["g"]["g"].rm.get_roles(name, domain)

    async def get_users_for_role_in_domain(self, name, domain):
        """gets the users that has a role inside a domain."""
        return self.model.model["g"]["g"].rm.get_users(name, domain)

    async def add_role_for_user_in_domain(self, user, role, domain):
        """adds a role for a user inside a domain."""
        """Returns false if the user already has the role (aka not affected)."""
        return await self.add_grouping_policy(user, role, domain)

    async def delete_roles_for_user_in_domain(self, user, role, domain):
        """deletes a role for a user inside a domain."""
        """Returns false if the user does not have any roles (aka not affected)."""
        return await self.remove_filtered_grouping_policy(
            0, user, role, domain
        )

    async def get_permissions_for_user_in_domain(self, user, domain):
        """gets permissions for a user or role inside domain."""
        return await self.get_filtered_policy(0, user, domain)
