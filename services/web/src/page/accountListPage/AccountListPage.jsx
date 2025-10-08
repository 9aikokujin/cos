import PageHeader from "@/components/pageHeader/PageHeader";
import AccountList from "@/components/accountList/AccountList";

import API from "@/api";
import { useAuth } from "@/store/AuthStore/main";
import { useScrollWithSearch } from "@/hooks/useScrollAndSearch";
import { useInput } from "@/hooks/useInput";

const AccountListPage = () => {
  const { token } = useAuth();
  const { debouncedValue, value, setValue } = useInput("", 300);
  const fetchAccount = async ({ page, size, search }) => {
    const res = await API.user.getAllChanels({
      page,
      size,
      token,
      name_channel: search,
    });
    return {
      items: res.channels,
      pagination: res.pagination,
    };
  };

  const { items: accounts, setLastItemRef } = useScrollWithSearch({
    fetchFn: fetchAccount,
    searchTerm: debouncedValue,
    pageSize: 10,
  });

  return (
    <>
      <PageHeader isShowBtns={true} type={"account"} onSearch={setValue} term={value} />
      <AccountList account={accounts} lastAccountElementRef={setLastItemRef} />
    </>
  );
};

export default AccountListPage;
