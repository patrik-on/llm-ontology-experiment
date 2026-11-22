import java.util.List;

final class ProductCatalog {
    String findFirst(List<String> products, String query) {
        if (products == null || query == null) {
            return null;
        }
        for (String product : products) {
            if (query.equals(product)) {
                return product;
            }
        }
        return null;
    }
}
