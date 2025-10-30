import { useAccountStore } from "@/app/store/entity/store";
import { useInfiniteScroll } from "@/hooks/useInfiniteScroll";
import { useFilterStore } from "@/app/store/filter/store";

import API from "@/app/api";
import { getSocialIcon } from "@/shared/utils/socialIcon";

import SearchInput from "@/components/searchInput/SearchInput";
import { useMultiSelectFilter } from "@/hooks/useMultiSelectFilter";

const fetchAccounts = async (page, term, filter) => {
  const params = { page };

  if (term) {
    params.name_channel = term;
  }

  if (filter?.channel_type) {
    params.type = filter.channel_type.toLowerCase();
  }

  const response = await API.account.getAccounts(params);
  return response;
};

const AccountFilter = () => {
  const setAccountId = useFilterStore((s) => s.setFilterChannelId);
  const filteredAccounts = useFilterStore((s) => s.filter.channel_id);

  const { items, isLoading, lastItemRef } = useInfiniteScroll(
    useAccountStore,
    fetchAccounts,
    "channels"
  );
  const { selected, toggleSelect } = useMultiSelectFilter(
    "Применить",
    (account) => {
      setAccountId(account.join(""));
    },
    false,
    () => {
      setAccountId("");
    },
    filteredAccounts
  );
  return (
    <div className="account_filter _flex_col_center">
      <h2>Аккаунты</h2>
      <div className="account_search">
        <SearchInput store={useAccountStore} placeholder="Поиск" alwaysExpanded width={"100%"} />
      </div>
      <ul className="account_list _flex_col_center">
        {items.map((account, i) => (
          <li
            key={account.id}
            ref={account.id === items.length - 1 ? lastItemRef : null}
            className={`filter_item _flex_center ${selected.includes(account.id) ? "_active" : ""}`}
            onClick={() => toggleSelect(account.id)}
          >
            <div className="account_social_pic" style={{ marginRight: 10 }}>
              <img src={getSocialIcon(account?.type)} alt="insta" />
            </div>
            <p className="_name">{account.name_channel}</p>
          </li>
        ))}
        {items.length === 0 && <p className="empty_result">Ничего не найдено</p>}
      </ul>
    </div>
  );
};

export default AccountFilter;
