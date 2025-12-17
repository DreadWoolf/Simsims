"Module for simsims simulation world."
import random
from abc import ABC, abstractmethod
import time
from datetime import date
import threading as th
from simsims_analytics import SimsimsAnalytics

#############################
#     World - hand of god   #
#############################
class World: # Model
    """
    Represents a simulated world environment with resources,
    a small settlement, and simulates how the world changes from
    day to day.
    The class prioritized wich transtion should resolve first, and
    tries to adapt the settlement to make it survive the longest.
    It handle the places and transtions for the settlement.

    Attributes:
        sleep_time (float): If the user want to slow down the day iteration.
        __end_of_the_world (bool): Has the world come to an end, end the simulation.
        __analytics (SimSimsAnalytics): Track the daily data from the simulation.
        __day: Track the day, the simulation is on.
        
    Methods:
        decrease_prio(resource, producer):
            Decreases priority since we created this resource.
        lack_of_resources(transition, places):
            Handles resource shortage conditions, adjusting priorities as needed.
        __restock_resource(from_place, to_place):
            Moves resources from overflowing place to another emptier place.
        overflowing_resource(places):
            Manages overflow of resources.
        create_place(place): Adds a new place to the world environment.
        create_transition(transition):
            Initiates a new transition process, and start the transtion thread.
        transition_connect(transition, old_connection):
            Establishes connections for transtions to places.
        tick(): The uppdate method.
        __result_of_day(): Handels the days result in increase or decrease of resources.
        export_to_excel(): Exports simulation data to an Excel file for analysis.
    """
    def __init__(
            self,
            starting_settlement = 40,
            strating_resources = 80,
            sleep_time = 1
            ) -> None:
        self.__day = 0
        self.sleep_time = sleep_time
        self.__end_of_the_world = False
        self.__analytics: SimsimsAnalytics

        self.__priority: dict[Transition, int] = {}
        self.__transistions: dict[Transition, list[Transition]] = {}
        self.__places: dict[Place, list[Place]] = {}

        self.__thread_observer = self.ThreadObserver()
        self.__lock = th.RLock()

        barack = Barack(self)
        self.create_place(barack)

        # Populate the barack
        for _ in range(starting_settlement):
            barack.store(Worker())

        warehouse = Warehouse(self)
        barn = Barn(self)
        self.create_place(warehouse)
        self.create_place(barn)

        for _ in range(0, strating_resources):
            if not random.randint(0,1):
                barn.store(Food())
            else:
                warehouse.store(Product())

        # Create a small initial settlement.
        for _ in range(0,4):
            self.create_transition(Factory(self))
            self.create_transition(Fields(self))
            self.create_transition(Dining(self))
            self.create_transition(Home(self))
            self.create_transition(Home(self))


        table_columns = ['Worker', 'Product', 'Food']

        self.__analytics = SimsimsAnalytics('Simsims_db.db', table_columns)
        self.__analytics.drop_table() # Make sure we use fresh table.
        self.__analytics.create_table()

    # def decrease_prio(self, resource: 'Resource', producer: 'Transition'):
    def decrease_prio(self, producer: 'Transition'):
        key = str(type(producer).__name__)
        if key not in self.__priority:
            self.__priority[key] = 0
        elif producer.producer_of != None:
            self.__priority[key] = max(0, self.__priority[key] - 1)

    def lack_of_resources(self, transition: 'Transition', places: list['Place']):
        self.__lock.acquire()
        if self.__end_of_the_world:
            self.__lock.release()
            return

        assert len(places) > 0
        key = str(type(transition).__name__)
        # Also check amount of resource overall, should this place be removed.
        for place in places:
            if len(place) == 0:
                amount = 0
                for place_in_list in self.__places[str(type(place).__name__)]:
                    # len of Place in list will give resource amount.
                    amount = amount + len(place_in_list)

                # If exists more than one place of this place_type,
                #  and total amount is less than half the capacity in each of this type.
                identical_place = len(self.__places[str(type(place).__name__)])
                if identical_place > 1 and amount < (place.capacity // 2) * identical_place:
                    for tmp_transition in self.__transistions[key]:
                        # Reconect the transistions from this transistion.
                        self.transition_connect(transition= tmp_transition, old_connection= place)
                    for index, place_in_list in enumerate(self.__places[str(type(place).__name__)]):
                        if self.__places[str(type(place).__name__)][index] == place:
                            self.__places[str(type(place).__name__)].pop(index)

                self.__raise_priority(transition, place)
            else:
                self.transition_connect(transition, old_connection= place)

        self.__lock.release()


    def __raise_priority(self, transition: 'Transition', place: 'Place'):
        "Raise priority for this resouce."
        # Every Raise priority key in transiton.
        for rp_key in self.__transistions:
            if self.__transistions[rp_key][0].producer_of == place.handle_resource:
                if rp_key in self.__priority:
                    self.__priority[rp_key] += 1
                    if (self.__priority[rp_key] > 5 and
                        self.__transistions[rp_key][0].max_amount >
                        len(self.__transistions[rp_key])):

                        blueprint = type(self.__transistions[rp_key][0])(self)
                        self.create_transition(blueprint)
                else:
                    if transition.producer_of is not None:
                        self.__priority[rp_key] = 1
                    else:
                        self.__priority[rp_key] = 0


    def __restock_resource(self, from_place: 'Place', to_place: 'Place'):
        for _ in range(0, from_place.capacity // 2):
            resource = from_place.retrieve()
            to_place.store(resource)

    def overflowing_resource(self, places: list['Place']):
        selected_place:Place = None

        for place in places:
            amount = 0
            place_name = str(type(place).__name__)
            for place_in_list in self.__places[place_name]:
                amount = amount + len(place_in_list)

            if amount > place.capacity * len(self.__places[place_name]):
                # Create a new identical place, aka blueprint and store some there.
                blueprint = type(self.__places[place_name][0])(self)
                selected_place = blueprint
                self.__places[place_name].append(blueprint)

            if len(place) >= place.capacity:
                # Check if we created a new place, otherwise randomize for one.
                if selected_place == None:
                    random.shuffle(self.__places[place_name])
                    selected_place = self.__places[place_name][0]

                # Make sure the selected place can recieve the resources,
                #   Otherwise create a new of the same type.
                if len(place) // 2 < selected_place.capacity - len(selected_place):
                    self.__restock_resource(from_place= place, to_place= selected_place)
                else:
                    blueprint = type(self.__places[place_name][0])(self)
                    selected_place = blueprint
                    self.__places[place_name].append(blueprint)
                    self.__restock_resource(from_place= place, to_place= selected_place)

    @property
    def Days(self):
        return str(self.__day)

    @property
    def check_endOfTheWorld(self) -> bool:
        for place in self.__places:
            amount = 0
            for building in self.__places[place]:
                amount += len(building)

            if place == 'Barack' and amount == 0:
                self.__end_of_the_world = True

        return self.__end_of_the_world

    def create_place(self, place : 'Place'):
        assert isinstance(place, Place)

        key = str(type(place).__name__)
        if key not in self.__places.keys():
            self.__places[key] = []

        self.__places[key].append(place)

    def create_transition(self, transition: 'Transition'):
        assert isinstance(transition, Transition)

        key = str(type(transition).__name__)
        if key not in self.__transistions.keys():
            self.__transistions[key] = []

        self.transition_connect(transition)
        self.__transistions[key].append(transition)
        transition.start() # Start the transition thread.
        if key not in self.__priority:
            self.__priority[key] = 0


    def transition_connect(self, transition: 'Transition', old_connection: 'Place' = None):
        for blueprint in transition.c_in_blueprint:
            self.connect_logik(transition, blueprint, in_connect= True,
                            out_connect= False, old_connection = old_connection)
        for blueprint in transition.c_out_blueprint:
            self.connect_logik(transition, blueprint, in_connect= False,
                               out_connect= True, old_connection = old_connection)

    def connect_logik(self, transition: 'Transition', connection,
                      in_connect = False, out_connect = False, old_connection = None):
        if in_connect:
            for place in self.__places:
                random.shuffle(self.__places[place])
                if (isinstance(self.__places[place][0], connection) and
                        self.__places[place][0] != old_connection):
                    transition.connect_in(self.__places[place][0])

        if out_connect:
            for place in self.__places:
                random.shuffle(self.__places[place])
                if (isinstance(self.__places[place][0], connection) and
                        self.__places[place][0] != old_connection):
                    transition.connect_out(self.__places[place][0])


    def thread_finished(self, thread):
        self.__thread_observer.finished(thread)

    def add_thread(self, new_thread):
        self.__thread_observer.add_thread(new_thread)

    class ThreadObserver:
        "Inner class that keeps track of the transition threads."
        def __init__(self):
            self.__thread_list: list[th.Thread] = []
            self.__thread_limit = 10 # 5
            self.new_thread = th.Event()
            self.all_finished = th.Event()
            self.__still_ticking = False
            self.lock = th.Lock()

        def add_thread(self, thread):
            if len(self.__thread_list) < self.__thread_limit:
                self.__thread_list.append(thread)

        def finished(self, f_thread):
            self.lock.acquire()
            for i, thread in enumerate(self.__thread_list):
                if f_thread == thread:
                    self.__thread_list.pop(i)
                    self.new_thread.set()
            self.lock.release()
            if self.__still_ticking and len(self.__thread_list) == 0:
                self.all_finished.set()
                self.__still_ticking = False

        @property
        def limit(self) -> bool:
            return len(self.__thread_list) + 1 > self.__thread_limit

        def ticking(self, still_ticking):
            self.__still_ticking = still_ticking



    def tick(self):
        worker_amount = 0
        # Check so we have places and transitions.
        for transition in self.__transistions:
            assert len(self.__transistions[transition]) > 0
        for place in self.__places:
            assert len(self.__places[place]) > 0

        # Logic to produce what is prioritized.
        produce_prio = sorted(self.__priority, key=self.__priority.get, reverse=True)

        # Limit iterations based on existing workers.
        for barack in self.__places['Barack']:
            worker_amount = worker_amount + len(barack)

        self.__thread_observer.ticking(still_ticking= True)
        for producer in produce_prio:
            iterations = worker_amount // 10 + (len(produce_prio) * 2)
            for transition in self.__transistions[producer]:

                if iterations > 0:
                    # If limit is reached we wait for a thread to finsih.
                    if not self.__thread_observer.limit:
                        transition.continue_run()
                        self.__thread_observer.add_thread(transition)
                    else:
                        self.__thread_observer.new_thread.wait()
                        self.__thread_observer.new_thread.clear()
                    iterations = iterations - 1

        if not self.__thread_observer.all_finished.is_set():
            self.__thread_observer.all_finished.wait()
            self.__thread_observer.all_finished.clear()

        transition_length = 0
        for place in self.__transistions:
            transition_length = transition_length + len(self.__transistions[place])
        if (self.__day + 1) % transition_length == 0:
            for place in self.__transistions:
                for transition in self.__transistions[place]:
                    self.transition_connect(transition)
            time.sleep(self.sleep_time)

        return self.__result_of_day()


        #########################################
        # Some logs in the terminal for the days result.
        #########################################
    def __result_of_day(self) -> bool:
        print(f"Result of the day: {self.__day}", end= "")
        data = []

        for place in self.__places:
            resource_of_place = sum(len(building) for building in self.__places[place])
            if place == 'Barack' and resource_of_place == 0:
                self.__end_of_the_world = True

            print(f"\n{self.__places[place][0]} {resource_of_place}", end="")
            time.sleep(self.sleep_time * 0.2)
            data.append(resource_of_place)

        print()
        for place in self.__places:
            print(f"{place}: {len(self.__places[place])}", end=" ")
        print()
        for transition in self.__transistions:
            print(f"{transition}: {len(self.__transistions[transition])}", end=" ")

        # Add the day, to the database.
        # self.__analytics.add_step(self.__Day, data = tuple(data))
        self.__analytics.add_step(data = tuple(data))

        if not self.__end_of_the_world:
            self.__day += 1
            print("\n")
        else: # End of the Civilization.
            for key in self.__transistions:
                for transition in self.__transistions[key]:
                    transition.stop()
            self.__transistions = {}
            self.__places = {}
            self.export_to_excel()
            print(f"\nThe civilisation lasted: {this_world.Days} days.")
            self.__analytics.to_figure("Simsim_graph")
        return self.__end_of_the_world


    def export_to_excel(self):
        filename = 'Simsims_' + str(date.today())
        self.__analytics.to_excel(filename= filename)


#############################
#         Resource          #
#############################
class Resource:
    """
Resource class serving as a base type for all resource entities within the world model.

Methods:
    __init__ (): Initializes a new instance of the Resource class.
"""
    def __init__(self) -> None:
        pass


class Worker(Resource):
    """
Worker class representing a workers, a resource type within the world model.

This class extends the Resource base class and includes functionality to manage the 
worker's lifespan. Workers have a longevity value that can change over time, impacting 
their living status as (alive or deceased).

Attributes:
    is_alive (bool): Property indicating whether the worker is alive or not.

Methods:
    __init__ (): Initializes a new instance of the Worker class with a random longevity 
        value between 10 and 100.
    longevity_change(change: int): Updates the worker's longevity, ensuring it stays 
        within the range of 0 to 100.
"""
    def __init__(self):
        super().__init__()
        self.__longevity = random.randint(10,100) # 100


    def longevity_change(self, change: int):
        self.__longevity = max(min(self.__longevity + change, 100), 0)

    @property
    def is_alive(self):
        return True if self.__longevity > 0 else False


class Food(Resource):
    """
Food class representing a specific resource type in the world, with quality tha will impact.

This class extends the Resource base class, initializing food with a quality value that is 
capped at a maximum of 100 (meaning the food is of highest quality).
The quality will be representing potential food poisioning. The subclass is also able to
have basic rotting functionality implemented in the future.

Attributes:
    quality (int): The quality of the food item, maximum of 100.

Methods:
    __init__(initial_quality): Initializes a new instance of the Food class with a quality 
        value (defaulting between 40 and 100).
"""

    def __init__(self, initial_quality = random.randint(40, 100)):
        super().__init__()
        self.__quality: int = min(initial_quality, 100)

    @property
    def quality(self):
        return self.__quality


class Product(Resource):
    """
Product class representing a resource type within the world, specifically for 
products that can be stored and managed in various locations.

This class extends the Resource base class, allowing for possible product-specific
functionality to be implemented in the future.

Methods:
    __init__(): Initializes a new instance of the Product class, inheriting from 
        the Resource class.
"""
    def __init__(self):
        super().__init__()




#############################
#           Places          #
#############################
class Place(ABC):
    """
Place class serving as an abstract base class for various storage locations,
designed to manage resources in a controlled environment.

The Place class establishes functionality for storing and retrieving resources,
including reentrant locks, to control the transitions/threads. It provides an interface 
for subclasses to implement specific storage mechanisms and resource types, ensuring 
that all storage locations follows same foundation logic.

Attributes:
    _storage (list[Resource]): List to hold resources managed by the Place.
    _capcity (int): Maximum capacity of the Place, defining how many resources it can store.
    _world_controll (World): Reference to the world/model simulation controller.
    __lock (RLock): Reentrant lock for managing multiple access of the same transition
        to acces resources.

Methods:
    handle_resource (str): Abstract property to specify the type of resource handled by 
        subclasses.
    store(Resource): Public method to add a resource to the storage while managing access.
    _store(Resource): Abstract method to implement the actual storing logic in subclasses.
    capacity (int): Abstract property to return the maximum capacity of the Place.
    __len__ () -> int: Abstract method to return the current number of resources in storage.
    __str__ () -> str: Abstract method for string representation of the Place.
    __repr__ () -> str: Provides a string representation of the Place object type.
    retrieve() -> Resource: Public method to remove and return a resource from storage 
        while managing transition/thread access.
    _retrieve() -> Resource: Abstract method to implement the actual retrieval logic 
        in subclasses.
"""
    def __init__(self, world: World) -> None:
        self._storage: list[Resource] = []
        self._capcity = 20
        self._world_controll = world
        self.__lock = th.RLock() # Reentrant lock.

    @property
    def handle_resource(self):
        raise NotImplementedError

    def store(self, resource: Resource):
        self.__lock.acquire()
        self._store(resource)
        self.__lock.release()

    @abstractmethod
    def _store(self, resource: Resource): ...

    @property
    def capacity(self) -> int:
        raise NotImplementedError

    @abstractmethod
    def __len__(self): ...

    @abstractmethod
    def __str__(self) -> str: ...

    def __repr__(self) -> str:
        return str(type(self).__name__)

    def retrieve(self) -> Resource: # queue standrad = "LIFO"
        self.__lock.acquire()
        resource = self._retrieve()
        self.__lock.release()
        return resource

    @abstractmethod
    def _retrieve(self) -> Resource: ...


class Barack(Place):
    """
Barack class representing a facility for managing and storing Worker entities in a 
FIFO (First In, First Out) manner within the world model.

This class inherits from the Place class and includes specialized methods to add, retrieve, 
and check if the Workers is alvive. It ensures workers are stored after the storage capacity,
handeling the overflow through the world model.
The Barack class is specifically designed to manage Workers as a waiting space,
untill the workers are fetched from any transition facillity.

Attributes:
    _world_controll (World): Reference to the world/model simulation controller.
    capacity (int): The maximum storage capacity of the Barack.
    handle_resource (str): Specifies the type of resource the Barack manages ("Worker").

Methods:
    __str__ (): Returns a string representation of the workers in the Barack.
    _retrieve () -> Worker: Retrieves the first Worker in storage. (FIFO)
    __check_living (): Checks for non-living workers and removes them from storage.
    __len__ () -> int: Returns the number of living Worker items in storage.
    _store (Worker): Adds a Worker to storage, but also managing capacity, and 
    resource overflow.
"""
    def __init__(self, world: World) -> None:
        super().__init__(world)
        self._world_controll = world

    def __str__(self) -> str:
        return "Workers in barack: "

    @property
    def capacity(self) -> int:
        return self._capcity

    @property
    def handle_resource(self):
        return str(type(Worker).__name__)


    def _retrieve(self) -> Worker:
        assert len(self._storage) > 0
        return self._storage.pop(0) # FIFO - First in first out.

    def __check_living(self):
        for index, worker in enumerate(self._storage):
            if not worker.is_alive:
                self._storage.pop(index)

        for index, worker in enumerate(self._storage):
            worker: Worker
            if not worker.is_alive:
                self._storage.pop(index)

    def __len__(self):
        self.__check_living()
        if len(self._storage) <= 0:
            return 0
        return len(self._storage)

    def _store(self, resource: Worker):
        # control the attribut, before storing.
        if not isinstance(resource, Worker):
            raise TypeError()

        if len(self._storage) > self._capcity:
            self._world_controll.overflowing_resource([self])
        if resource.is_alive:
            self._storage.append(resource)
            self.__check_living()

class Warehouse(Place):
    """
Warehouse class representing a storage facility for Product entities within the world model, 
using a LIFO (Last In, First Out) retrieval system.

This class inherits from the Place class and is designed to store and manage Product resources. 
It includes methods to add and retrieve Product entities, handle storage capacity, 
and interact with the world/modell simulation controller to address overflow situations.
The Warehouse class is specialized for managing Product resources.

Attributes:
    _world_controll (World): Reference to the world/model simulation controller.
    handle_resource (str): Specifies the type of resource the Warehouse manages ("Product").
    capacity (int): Maximum capacity of the Warehouse for storing Product items.

Methods:
    __str__ (): Returns a string representation of products in the Warehouse.
    _retrieve () -> Product: Retrieves the most recently stored Product item (LIFO).
    _store (Product): Adds a Product to storage, managing capacity and overflow.
    __len__ () -> int: Returns the current number of Product items in storage.
"""

    def __init__(self, world: World) -> None:
        super().__init__(world)
        self._world_controll = world

    @property
    def handle_resource(self):
        return str(type(Product).__name__)

    @property
    def capacity(self) -> int:
        return self._capcity

    def __str__(self) -> str:
        return "Products in warehouse: "

    def _retrieve(self) -> Product:
        assert len(self._storage) > 0
        return self._storage.pop() # LIFO - Last in First out.

    def _store(self, resource: Product):
        # control the attribut, before storing.
        if not isinstance(resource, Product):
            raise TypeError()

        if len(self._storage) > self._capcity:
            self._world_controll.overflowing_resource([self])
        self._storage.append(resource)

    def __len__(self):
        if len(self._storage) <= 0:
            return 0
        return len(self._storage)


class Barn(Place):
    """
Barn class representing a storage facility, which stores food.

This class extends the Place class, with specific functionality to store, retrieve, and 
manage Food resources in a FIFO (First In, First Out) manner. It has a capacity management,
and handles overflow by interacting with the world/modell simulation controller.

Attributes:
    _world_controll (World): Reference to the world/model simulation controller.
    handle_resource (str): Specifies the type of resource the Barn manages ("Food").
    capacity (int): The maximum capacity of the Barn,
    limiting the number of Food that can be stored.

Methods:
    __str__ (): Returns a string representation of the Barn's contents.
    __repr__ (): Provides representation of the Barn object.
    _retrieve () -> Food: Retrieves the first Food item in storage (FIFO).
    _store (Food): Adds a Food resource to storage, managing capacity and overflow.
    __len__ () -> int: Returns the current number of Food items in storage.
"""
    def __init__(self, world: World) -> None:
        super().__init__(world)
        self._world_controll = world

    @property
    def handle_resource(self):
        return str(type(Food).__name__)

    @property
    def capacity(self) -> int:
        return self._capcity

    def __str__(self) -> str:
        return "Food in barn: "

    def __repr__(self) -> str:
        return "Barn"

    def _retrieve(self) -> Food:  # FIFO
        assert len(self._storage) > 0
        return self._storage.pop(0) # FIFO - First in first out.

    def _store(self, resource: Food):
        # control the attribut, before storing.
        if not isinstance(resource, Food):
            raise TypeError()

        if len(self._storage) > self._capcity:
            self._world_controll.overflowing_resource([self])
        self._storage.append(resource)

    def __len__(self):
        if len(self._storage) == 0:
            return 0
        return len(self._storage)


#############################
#       Transitions         #
#############################
class Transition(ABC, th.Thread):
    """
Transition class representing an abstract base class for transition entities in a world model, 
designed to manage input and output connections, it makes each transition act as a thread,
which is control event-based.

This class extends Python's Thread class, enabling it to manage independent processes within 
the world model. It sets up the control flow for derived classes through abstract methods, 
and allows specific behaviors. The class controls resource fetching for subclasses,
and manages thread lifecycle events (start, pause, continue, and stop).

Attributes:
    _world_controller (World): Reference to the world/model simulation controller.
    __max_amount (int): Maximum amount of transitons for that transtion type.
    _running (bool): Control flag for managing the thread lifecycle.
    continue_event (Event): Threading event to manage when the thread should work.
    finish_event (Event): Threading event indicating that it is finished 
        (for world inner class, that manages the active threads).

Methods:
    max_amount (int): Returns the maximum amount of transitions of this transition type.
    c_in_blueprint (list[Place]): Abstract property to define input connections.
    c_out_blueprint (list[Place]): Abstract property to define output connections.
    producer_of (str): Abstract property to specify the resource type produced by subclasses.
    fetchable_resource (bool): Returns whether a resource is available from the input connection.
    connect_in (Place): Connects an input resource location to the transition.
    connect_out (Place): Connects an output resource location to the transition.
    tick (): Executes the core operation defined in the subclass `_tick` method.
    continue_run (): Signals the thread/this transition to resume it's work.
    finish (): Called when the transition/thread is finished.
    thread_work_finished (bool): Returns True if finish_event is set.
    pause (): Pauses the thread by clearing the continue event (turn of the green light).
    start (): Initiates the transition to 'be a thread'.
    run (): Main thread loop managing the transitions operations.
    stop (): Signals the thread to cease operation.
"""
    def __init__(self, world: World) -> None:
        super().__init__()  # Initialize the Thread superclass.
        self._world_controller = world
        self.__max_amount = 50
        self._running = True  # Control flag for the thread.

        # Thread events.
        self.continue_event = th.Event()
        self.finish_event = th.Event()

    @property
    def max_amount(self):
        return self.__max_amount

    @property
    @abstractmethod
    def c_in_blueprint(self) -> list[Place]:
        pass

    @property
    @abstractmethod
    def c_out_blueprint(self) -> list[Place]:
        pass

    @property
    @abstractmethod
    def producer_of(self) -> str:
        pass

    def fetchable_resource(self, in_connection: Place) -> bool:
        return self._fetchable_resource(in_connection)

    @abstractmethod
    def _fetchable_resource(self, in_connection: Place) -> bool:
        pass

    def connect_in(self, connect: Place):
        self._connect_in(connect)

    @abstractmethod
    def _connect_in(self, connect: Place):
        pass

    def connect_out(self, connect: Place):
        self._connect_out(connect)

    @abstractmethod
    def _connect_out(self, connect: Place):
        pass

    def __repr__(self) -> str:
        return str(type(self).__name__)

    def tick(self):
        self._tick()

    def _tick(self):
        raise NotImplementedError(self)

    def continue_run(self):
        # self.pause_event.clear()
        self.continue_event.set()

    def finish(self):
        self.pause()
        self._world_controller.thread_finished(self)

    def thread_work_finished(self) -> bool:
        return self.finish_event.is_set()

    def pause(self):
        "Pause/Turn of continue for this transition (it is a thread)."
        self.continue_event.clear()

    # Thread start method.
    def start(self):
        self._running = True
        super().start()

    # Thread run method.
    def run(self):
        while self._running:
            if self.continue_event.is_set():
                self.tick()
                self.finish()
            else:
                self.continue_event.wait()

    def stop(self):
        """Stop the thread completely."""
        self._running = False
        self.continue_event.set()

    def __del__(self):
        self.stop()


class Factory(Transition):
    """
Factory class representing a manufacturing facility where workers produce products, 
but it comes with a risk of the workers ending up in an accident.

This class extends the Transition class and models a factory setting where workers engage 
in production, wich consume longevity in each cycle. The class retrieve workers from baracks
and sends them to baracks afterwards (if the worker survived). If the worker
survived, it also stores a new product in the connected warehouse.

Attributes:
    _world_controller (World): Reference to the world/modell simulation controller.
    _longevity_cost (int): Decreases worker longevity each production cycle.
    _accident_prob (int): Probability of a workplace accident, killing the worker.
    _out_warehouse (Place): Output warehouse connection, where products is stored.
    _in_barack (Place): Barrack connection for retrieving workers.
    _out_barack (Place): Barrack connection for sending back workers.
    __producer_of (type): Type of resource this factory produces (Product).

Methods:
    producer_of (str): Returns the type of resource produced as a string.
    c_in_blueprint (list[Place]): Blueprint for input connections.
    c_out_blueprint (list[Place]): Blueprint for output connections.
    _tick (): Processes a production cycle, with possible accidents.
    _fetchable_resource (Place): Checks if workers are available.
    __send_result (Worker): Sends produced product and workers back.
    _connect_in (Place): Connects input facilities to the factory.
    _connect_out (Place): Connects output facilities to the factory.
"""
    def __init__(self, world: World) -> None:
        super().__init__(world)
        self._world_controller = world
        self._longevity_cost: int = random.randint(5, 15)
        self._accident_prob = random.randint(3, 6)
        self.__producer_of = Product

        # Places.
        self._out_warehouse: Place
        self._in_barack: Place
        self._out_barack: Place

    @property
    def producer_of(self) -> str:
        return str(type(self.__producer_of).__name__)

    @property
    def c_in_blueprint(self) -> list[Place]:
        return [Barack]

    @property
    def c_out_blueprint(self) -> list[Place]:
        return [Barack, Warehouse]

    def _tick(self):
        if self._fetchable_resource(self._in_barack):
            worker: Worker = self._in_barack.retrieve()
        else:
            self._world_controller.lack_of_resources(self, [self._in_barack])
            return

        if random.randint(1, 10) > self._accident_prob:
            worker.longevity_change(-100)
            # print("Accident")
        else:
            worker.longevity_change(self._longevity_cost * -1)

        if worker.is_alive:
            self.__send_result(worker)
            # world.decrease_prio(self.producer_of, self)
            this_world.decrease_prio(self)

    def _fetchable_resource(self, in_connection: Place) -> bool:
        return len(in_connection) > 0

    def __send_result(self, worker: Worker):
        self._out_warehouse.store(Product())
        self._out_barack.store(worker)

    def _connect_in(self, connect: Warehouse):
        if isinstance(connect, Barack):
            self._in_barack = connect
        else:
            raise TypeError("Expected a Barack instance")

    def _connect_out(self, connect):
        if isinstance(connect, Warehouse):
            self._out_warehouse = connect
        elif isinstance(connect, Barack):
            self._out_barack = connect
        else:
            raise TypeError("Expected a Warehouse or Barack instance")


class Dining(Transition):
    """
Dining class representing a dining facility where workers consume food to 
increase longevity, with chance for food poisioning (reduceing instead).

This class extends the Transition class and simulates a dining environment where workers
eat food, increasing or decreasing their longevity depending on the quality of the food.
It manages connections with input facilities Barns and Barracks, aswell as
output facilities for sending back the workers after dining.

Attributes:
    _world_controller (World): Reference to the world/model of the simulation.
    _in_barn (Place): Input barn connection where food is stored.
    _in_barack (Place): Input barrack connection for retrieving workers.
    _out_barack (Place): Output barrack connection for returning workers.
    __use_resource (type): Type of resource consumed (Food).

Methods:
    producer_of (str): Returns the type of resource used as a string.
    c_in_blueprint (list[Place]): Blueprint for input connections.
    c_out_blueprint (list[Place]): Blueprint for output connections.
    _connect_in (Place): Connects input connections to the dining facility.
    _connect_out (Place): Connects output connections to the dining facility.
    _tick (): Processes a cycle for the dining facillity, where workers eat.
    _fetchable_resource (Place): Checks if resources are available.
    __send_result (Resource): Sends workers back after dining.
"""
    def __init__(self, world: World) -> None:
        super().__init__(world)
        self._world_controller = world
        self.__use_resource = Food
        # Places.
        self._in_barn: Place = None
        self._in_barack: Place
        self._out_barack: Place

    @property
    def producer_of(self) -> str:
        return str(type(self.__use_resource).__name__)

    @property
    def c_in_blueprint(self) -> list[Place]:
        return [Barack, Barn]

    @property
    def c_out_blueprint(self) -> list[Place]:
        return [Barack]

    def _connect_in(self, connect: Place):
        if isinstance(connect, Barack):
            self._in_barack = connect
        elif isinstance(connect, Barn):
            self._in_barn = connect
        else:
            raise TypeError("Expected a Barack or Barn instance")

    def _connect_out(self, connect: Place):
        if isinstance(connect, Barack):
            self._out_barack = connect
        else:
            raise TypeError("Expected a Barack instance")

    def _tick(self):
        worker: Worker = None
        food: Food = None

        if self.fetchable_resource(self._in_barack) and self.fetchable_resource(self._in_barn):
            worker = self._in_barack.retrieve()
            food = self._in_barn.retrieve()
            # Food is rotten/food poison if below 30 in quality.
            worker.longevity_change(round(food.quality - 30 * 0.2))
            self._world_controller.decrease_prio(self)
            self.__send_result(worker)
        else:
            self._world_controller.lack_of_resources(self, places=[self._in_barack, self._in_barn])

        if worker is not None:
            self.__send_result(worker)

    def _fetchable_resource(self, in_connection: Place) -> bool:
        return len(in_connection) > 0

    def __send_result(self, resource: Resource):
        self._out_barack.store(resource)


class Home(Transition):
    """
Home represents a residential building for workers and increase
worker longevity aswell as reproduction.

This class extends the Transition class to model homes where workers rests or
reproduce. It handles input and output facilities connected to the home
and determines for either reproduction or longevity increase for each
cycle. It has interactions with warehouses and barracks.

Attributes:
    _world_controller (World): Reference to the world simulation.
    __hometype (bool): Determines the action for each cycle, True is reproduction.
    _in_warehouse (Place): Input warehouse connection providing resources.
    __producer_of (type): Type of resource this home produces (Worker).

Methods:
    producer_of (str): Returns the resource produced as a string.
    c_in_blueprint (list[Place]): Blueprint for input connections.
    c_out_blueprint (list[Place]): Blueprint for output connections.
    _connect_in (Place): Connects input facilities.
    _connect_out (Place): Connects output facilities.
    _tick (): Processes a cycle of activity, either creating a new worker or enhancing longevity.
    _fetchable_resource (Place): Checks if resources are available from the input connection.
"""

    def __init__(self, world: World) -> None:
        super().__init__(world)
        self._world_controller = world
        self.__hometype: bool = False
        self.__producer_of = Worker

        # Places
        self._in_warehouse: Place = None
        self._in_barack: Place
        self._out_barack: Place

    @property
    def producer_of(self) -> str:
        return str(type(self.__producer_of).__name__)

    @property
    def c_in_blueprint(self) -> list[Place]:
        return [Barack, Warehouse]

    @property
    def c_out_blueprint(self) -> list[Place]:
        return [Barack]

    def _connect_in(self, connect: Place):
        if isinstance(connect, Warehouse):
            self._in_warehouse = connect
        elif isinstance(connect, Barack):
            self._in_barack = connect
        else:
            raise TypeError("Expected a Warehouse or Barack instance")

    def _connect_out(self, connect: Place):
        if isinstance(connect, Barack):
            self._out_barack = connect
        else:
            raise TypeError("Expected a Barack instance")

    def _tick(self):
        if (not self.fetchable_resource(self._in_warehouse) or
            not self.fetchable_resource(self._in_barack)):
            self._world_controller.lack_of_resources(self, [self._in_warehouse, self._in_barack])
            return

        self.__hometype = bool(random.randint(0, 1))  # True | False

        worker: Worker = self._in_barack.retrieve()
        self._in_warehouse.retrieve()  # Get a product, and destroy it

        # Either get a healthier worker or 1 new worker.
        if self.__hometype and len(self._in_barack) > 1:
            worker2 = self._in_barack.retrieve()
            self._out_barack.store(worker)
            self._out_barack.store(worker2)
            self._out_barack.store(Worker())  # The worker's child
            self._world_controller.decrease_prio(self)
        else:
            worker.longevity_change(5)
            self._out_barack.store(worker)

    def _fetchable_resource(self, in_connection: Place) -> bool:
        "return true if it is possible to fetch resources"
        return len(in_connection) > 0


class Fields(Transition):
    """
Fields class representing agricultural fields that produce food resources.

This class extends the Transition class to simulate the behavior of food production
from agricultural fields, connecting with various facilities such as barns, warehouses,
and worker barracks. It manages the input and output facilities required for production,
assesses accident probabilities for workers, and handles resource distribution.

Attributes:
    _world_controller (World): The world/ modell.
    _out_barn (Place): Output barn, store food.
    _accident_prob (int): Probabillity of worker accident.
    __producer_of (type): What resource this will produce.
    _in_barn (Barn): Input barn connection.
    _in_warehouse (Warehouse): Input warehouse connection.
    _in_barack (Barack): Input barracks for retrieving workers.

Methods:
    producer_of (str): Property for what resource is produced.
    c_in_blueprint (list[Place]): Blueprint for input connections.
    c_out_blueprint (list[Place]): Blueprint for output connections.
    _connect_in (Place): Connects input facilities to the field.
    _connect_out (Place): Connects output facilities to the field.
    _tick (): Processes a production cycle.
    __send_result (Worker): Sends produced resources to the output facilities.
    _fetchable_resource (Place): Checks if resources are available from the input connection.
"""
    def __init__(self, world: World) -> None:
        super().__init__(world)
        self._world_controller = world
        self._accident_prob = random.randint(3, 6)
        self.__producer_of = Food

        # Places.
        self._out_barn: Barn
        self._out_barack: Barack
        self._in_barack: Barack

    @property
    def producer_of(self) -> str:
        return str(type(self.__producer_of).__name__)

    @property
    def c_in_blueprint(self) -> list[Place]:
        return [Barack]

    @property
    def c_out_blueprint(self) -> list[Place]:
        return [Barack, Barn]

    def _connect_in(self, connect: Place):
        if isinstance(connect, Barack):
            self._in_barack = connect
        else:
            raise TypeError("Expected a Barack instance")

    def _connect_out(self, connect: Place):
        if isinstance(connect, Barn):
            self._out_barn = connect
        elif isinstance(connect, Barack):
            self._out_barack = connect
        else:
            raise TypeError("Expected a Barn or Barack instance")

    def _tick(self):
        worker: Worker

        if self.fetchable_resource(self._in_barack):
            worker = self._in_barack.retrieve()
        else:
            self._world_controller.lack_of_resources(self, [self._in_barack])
            return

        if random.randint(1, 10) < self._accident_prob:
            worker.longevity_change(-random.randint(10, 70))

        if worker.is_alive:
            self.__send_result(worker)
            self._world_controller.decrease_prio(self)

    def __send_result(self, worker: Worker):
        self._out_barn.store(Food(initial_quality=random.randint(20, 100)))
        self._out_barack.store(worker)

    def _fetchable_resource(self, in_connection: Place) -> bool:
        return len(in_connection) > 0


if __name__ == "__main__":
    ENDOFTHEWORLD = False

    STARTING_SETTLEMENT = 1000  # 40
    STARTING_RESOURCES = 1000   # 80
    SLEEP_TIME = 0
    this_world = World(STARTING_SETTLEMENT, STARTING_RESOURCES, SLEEP_TIME)

    while not ENDOFTHEWORLD:
        ENDOFTHEWORLD = this_world.tick()
    print("Done")
