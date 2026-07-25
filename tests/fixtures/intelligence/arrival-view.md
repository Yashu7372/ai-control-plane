# Repository Intelligence Report
## sample-arrival-view-service

### `src/main/resources/application.yml`

```yaml
messaging:
  bag-queue: VIEW.ARRIVAL.BAG.QMAIN
```

### `src/main/java/example/events/BagEventConsumer.java`

```java
package example.events;

public class BagEventConsumer {
    private final ConsumerFactory consumerFactory;
    private final BagEventFacade bagEventFacade;

    @Value("${messaging.bag-queue}")
    private String bagQueue;

    public void start() {
        consumerFactory.subscribe(bagQueue, true, BagMessageEvent.class)
            .doOnNext(result -> handle(result));
    }

    private void handle(ReceiverResult result) {
        bagEventFacade.process(result.getPayload());
    }
}
```

### `src/main/java/example/application/BagEventFacade.java`

```java
package example.application;

public interface BagEventFacade {
    void process(BagMessageEvent event);
}
```

### `src/main/java/example/application/BagEventFacadeImpl.java`

```java
package example.application;

public class BagEventFacadeImpl implements BagEventFacade {
    private final AfsArrivalBagDao afsArrivalBagDao;

    public void process(BagMessageEvent event) {
        afsArrivalBagDao.save(toWriteModel(event));
    }
}
```

### `src/main/java/example/domain/AfsArrivalBagDao.java`

```java
package example.domain;

public interface AfsArrivalBagDao {
    void save(BagWriteModel bag);
}
```

### `src/main/java/example/infrastructure/AfsArrivalBagDaoAdapter.java`

```java
package example.infrastructure;

public class AfsArrivalBagDaoAdapter implements AfsArrivalBagDao {
    private final AfsArrivalBagRepository repository;

    public void save(BagWriteModel bag) {
        repository.save(map(bag));
    }
}
```

### `src/main/java/example/infrastructure/AfsArrivalBagRepository.java`

```java
package example.infrastructure;

public interface AfsArrivalBagRepository extends JpaRepository<AfsArrivalBagEntity, String> {
}
```

### `src/main/java/example/infrastructure/AfsArrivalBagEntity.java`

```java
package example.infrastructure;

@Entity
@Table(name = "ARRIVAL_BAGS", schema = "VIEW_OWNER")
public class AfsArrivalBagEntity {
    private String bagTag;
}
```

### `src/main/java/example/events/BagMessageEvent.java`

```java
package example.events;

public class BagMessageEvent {
    private String bagTag;
    private String inboundFlight;
    private String station;
}
```
