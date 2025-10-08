import { useCallback } from "react";

import API from "@/api";
import { useAuth } from "@/store/AuthStore/main";
import { useScrollWithSearch } from "@/hooks/useScrollAndSearch";
import { useInput } from "@/hooks/useInput";

import ClientItem from "@/components/clientItem/ClientItem";
import PageHeader from "../pageHeader/PageHeader";

import "./AdminPage.css";

const AdminPage = () => {
  const { debouncedValue, value, setValue } = useInput("", 300);
  const { token } = useAuth();

  const fetchUsersSearch = async ({ page, size, search }) => {
    if (search) {
      const res = await API.user.searchUser({ page, size, token, name: search });
      return {
        items: res.users,
        pagination: res.pagination,
      };
    } else {
      const res = await API.user.getAll({ page, size });
      return {
        items: res.users,
        pagination: res.pagination,
      };
    }
  };

  const {
    items: users,
    setLastItemRef,
    updateItem,
    refetch,
  } = useScrollWithSearch({
    fetchFn: fetchUsersSearch,
    searchTerm: debouncedValue,
    pageSize: 10,
  });

  const handleUserUpdate = useCallback(
    (id, update) => {
      updateItem(id, update);
    },
    [updateItem]
  );

  return (
    <div className="admin_page container _flex_column">
      <PageHeader
        isShowBtns={true}
        type={"admin"}
        isFilter={false}
        onSearch={setValue}
        reset={refetch}
        term={value}
      />
      <div className="client__list _flex_column_center">
        {users?.map((user, index) => {
          if (users.length === index + 1) {
            if (!user) return null;
            return (
              <ClientItem
                user={user}
                ref={setLastItemRef}
                key={user.id}
                resetUser={(update) => handleUserUpdate(user.id, update)}
              />
            );
          }
          return (
            <ClientItem
              user={user}
              key={user.id}
              resetUser={(update) => handleUserUpdate(user.id, update)}
            />
          );
        })}
      </div>
    </div>
  );
};

export default AdminPage;
