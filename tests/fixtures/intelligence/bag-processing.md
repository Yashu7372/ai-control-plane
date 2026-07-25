# Repository Intelligence Report
## sample-bag-processing-service

### `src/main/java/example/service/AfsEventProducerService.java`

```java
package example.service;

public interface AfsEventProducerService {
    void publishBagProcessedEvent(BagProcessedEvent event);
}
```

### `src/main/java/example/service/AfsEventProducerServiceImpl.java`

```java
package example.service;

public class AfsEventProducerServiceImpl implements AfsEventProducerService {
    private final JmsTemplate eventTemplate;

    @Value("${topic.arrival-bag:OPS.ARRIVAL.BAG.PROCESSED}")
    private String arrivalBagTopic;

    public void publishBagProcessedEvent(BagProcessedEvent event) {
        eventTemplate.convertAndSend(arrivalBagTopic, event);
    }
}
```

### `src/main/java/example/service/CommonUpdatesService.java`

```java
package example.service;

public class CommonUpdatesService {
    private final AfsEventProducerService afsEventProducerService;

    public void performCommonUpdates(Bag bag) {
        saveBag(bag);
        afsEventProducerService.publishBagProcessedEvent(toEvent(bag));
    }

    private void saveBag(Bag bag) {
    }
}
```

### `src/main/java/example/events/BagProcessedEvent.java`

```java
package example.events;

public class BagProcessedEvent {
    private String bagTag;
    private String inboundFlight;
    private String station;
}
```
