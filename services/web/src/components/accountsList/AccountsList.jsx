import API from "@/app/api";

import { useInfiniteScroll } from "@/hooks/useInfiniteScroll";
import { useAccountStore } from "@/app/store/entity/store";

import AccountItem from "./components/AccountItem";
import Loader from "@/components/loader/Loader";

import "./AccountList.css";

const fetchAccounts = async (page, term, filter) => {
  const params = { page };

  if (term) {
    params.name_channel = term;
  }

  if (filter?.channel_type) {
    params.type = filter.channel_type;
  }

  const response = await API.account.getAccounts(params);
  return response;
};

const AccountsList = () => {
  const { items, isLoading, lastItemRef } = useInfiniteScroll(
    useAccountStore,
    fetchAccounts,
    "channels"
  );

  return (
    <div className="_flex_col_center" style={{ gap: 20, overflow: "auto", paddingBottom: 20 }}>
      {items?.map((item, i) => (
        <AccountItem
          key={item.id}
          ref={i === items.length - 1 ? lastItemRef : null}
          channel={item}
        />
      ))}
      {isLoading && <Loader />}
    </div>
  );
};

export default AccountsList;
